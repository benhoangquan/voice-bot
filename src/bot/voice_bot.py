from ..config import Config
import asyncio
from loguru import logger

# Pipecat Core
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import LLMRunFrame, EndFrame, TTSSpeakFrame

# Processors & Context
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIProcessor
from pipecat.services.llm_service import FunctionCallParams

# New Schemas Import
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema

# Turn Taking & VAD
from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import (
    TurnAnalyzerUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3

# Custom Adapters
from ..adapters.base import CalendarAdapter
from ..rag.menu_rag import MenuRAG
from ..guardrails.safety import Guardrails
from ..transfer.queue import TransferQueue, TransferRequest, TransferPriority

class VoiceBot:
    def __init__(
        self,
        stt_service,
        tts_service,
        llm_service,    
        calendar_adapter: CalendarAdapter,
        menu_rag: MenuRAG,
        guardrails: Guardrails,
        transfer_queue: TransferQueue,
        call_sid: str,
        caller_id: str
    ):
        self.stt = stt_service
        self.tts = tts_service
        self.llm = llm_service
        self.calendar_adapter = calendar_adapter
        self.menu_rag = menu_rag
        self.guardrails = guardrails
        self.transfer_queue = transfer_queue
        self.call_sid = call_sid
        self.caller_id = caller_id
        
        # 1. Initialize Smart Turn Analyzer
        logger.info("Loading Smart Turn Analyzer...")
        self.turn_analyzer = LocalSmartTurnAnalyzerV3()
        
        # 2. Define Function Schemas (The "Interface")
        # New Pattern: Use FunctionSchema objects instead of raw dicts
        self.menu_tool = FunctionSchema(
            name="query_menu",
            description="Query the restaurant menu for items and prices",
            properties={
                "question": {
                    "type": "string",
                    "description": "The customer's question about the menu"
                }
            },
            required=["question"]
        )

        self.reservation_tool = FunctionSchema(
            name="create_reservation",
            description="Create a restaurant reservation",
            properties={
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM"},
                "party_size": {"type": "integer"},
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"}
            },
            required=["date", "time", "party_size", "customer_name", "customer_phone"]
        )

        self.transfer_tool = FunctionSchema(
            name="transfer_to_staff",
            description="Transfer to human staff",
            properties={
                "reason": {"type": "string", "description": "Reason for transfer"}
            },
            required=["reason"]
        )

        # Bundle into ToolsSchema
        self.tools = ToolsSchema(standard_tools=[
            self.menu_tool, 
            self.reservation_tool, 
            self.transfer_tool
        ])

        # 3. Initialize Context with Tools
        # New Pattern: Pass tools to LLMContext, NOT to llm.tools directly
        self.messages = [
            {
                "role": "system",
                "content": self._create_system_prompt()
            }
        ]
        self.context = LLMContext(self.messages, self.tools)

        # 4. Register Implementations (The "Logic")
        self._register_function_handlers()

    def _create_system_prompt(self) -> str:
        return """You are a friendly and professional voice assistant for a restaurant reservation system. 
        Your role is to help customers make reservations, answer menu questions, and transfer to staff.
        Keep responses very concise and conversational."""

    def _register_function_handlers(self):
        """
        Binds Python functions to the LLM and sets up event handlers.
        """
        
        # --- A. Define Handlers ---
        
        async def query_menu(params: FunctionCallParams):
            question = params.arguments.get("question")
            results = self.menu_rag.query(question, n_results=3)
            if results:
                formatted = "\n".join([f"- {r['name']}: {r['description']} (${r['price']:.2f})" for r in results])
                await params.result_callback(f"Here are some menu items:\n{formatted}")
            else:
                await params.result_callback("I couldn't find any menu items matching that.")

        async def create_reservation(params: FunctionCallParams):
            args = params.arguments
            is_valid, error = self.guardrails.validate_reservation_info(args)
            if not is_valid:
                await params.result_callback(f"Issue with details: {error}")
                return

            available = await self.calendar_adapter.check_availability(
                args["date"], args["time"], args["party_size"]
            )
            if not available:
                await params.result_callback("That time slot is not available.")
                return

            result = await self.calendar_adapter.create_reservation(args)
            if "error" in result:
                await params.result_callback(f"Error creating reservation: {result['error']}")
            else:
                await params.result_callback(f"Reservation confirmed! Confirmation number: {result.get('reservation_id')}")

        async def transfer_to_staff(params: FunctionCallParams):
            reason = params.arguments.get("reason")
            request = TransferRequest(
                call_sid=self.call_sid,
                caller_id=self.caller_id,
                reason=reason,
                priority=TransferPriority.NORMAL
            )
            position = await self.transfer_queue.enqueue_transfer(request)
            await params.result_callback(f"Transferring you now. Your position is {position}.")

        # --- B. Register with LLM Service ---
        self.llm.register_function("query_menu", query_menu)
        self.llm.register_function("create_reservation", create_reservation)
        self.llm.register_function("transfer_to_staff", transfer_to_staff)

        # --- C. Latency Masking (New Feature) ---
        # When the LLM decides to call a function, immediately say "Let me check..." 
        # to fill the dead air while RAG/DB work happens.
        @self.llm.event_handler("on_function_calls_started")
        async def on_function_calls_started(service, function_calls):
            # We can check function_calls[0].name if we want specific fillers for specific tools
            await self.tts.queue_frame(TTSSpeakFrame("Let me check on that for you."))

    async def run(self, transport, handle_sigint=True):
        """Builds and runs the pipeline with the provided transport."""
        
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            self.context,
            user_params=LLMUserAggregatorParams(
                user_turn_strategies=UserTurnStrategies(
                    stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=self.turn_analyzer)]
                ),
            ),
        )

        rtvi = RTVIProcessor()

        pipeline = Pipeline([
            transport.input(),
            rtvi,
            self.stt,
            user_aggregator,
            self.llm,
            self.tts,
            transport.output(),
            assistant_aggregator,
        ])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[RTVIObserver(rtvi)],
        )

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("User joined. Triggering greeting...")
            self.messages.append({"role": "system", "content": "Say hello and ask how you can help with their order."})
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("User disconnected.")
            await task.cancel()

        logger.info("Pipeline starting...")
        runner = PipelineRunner(handle_sigint=handle_sigint)
        await runner.run(task)