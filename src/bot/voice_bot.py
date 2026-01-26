from loguru import logger

# Pipecat Core
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import LLMRunFrame, EndFrame

# Processors & Context
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIProcessor
from pipecat.services.llm_service import FunctionCallParams

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
        
        # 1. Initialize Smart Turn Analyzer (Loads model - might take a few seconds)
        logger.info("Loading Smart Turn Analyzer...")
        self.turn_analyzer = LocalSmartTurnAnalyzerV3()
        
        # 2. Define Tools
        self._register_tools()
        
        # 3. Initialize Context
        self.messages = [
            {
                "role": "system",
                "content": self._create_system_prompt()
            }
        ]
        self.context = LLMContext(self.messages)

    def _create_system_prompt(self) -> str:
        return """You are a friendly and professional voice assistant for a restaurant reservation system. 
        Your role is to help customers make reservations, answer menu questions, and transfer to staff.
        Keep responses very concise and conversational."""

    def _register_tools(self):
        # Define Tool Schemas
        self.llm.tools = [
            {
                "type": "function",
                "function": {
                    "name": "query_menu",
                    "description": "Query the restaurant menu for items and prices",
                    "parameters": {
                        "type": "object",
                        "properties": {"question": {"type": "string"}},
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_reservation",
                    "description": "Create a restaurant reservation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "time": {"type": "string"},
                            "party_size": {"type": "integer"},
                            "customer_name": {"type": "string"},
                            "customer_phone": {"type": "string"}
                        },
                        "required": ["date", "time", "party_size", "customer_name", "customer_phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "transfer_to_staff",
                    "description": "Transfer to human staff",
                    "parameters": {
                        "type": "object",
                        "properties": {"reason": {"type": "string"}},
                        "required": ["reason"]
                    }
                }
            }
        ]

        # Register Handlers
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

        self.llm.register_function("query_menu", query_menu)
        self.llm.register_function("create_reservation", create_reservation)
        self.llm.register_function("transfer_to_staff", transfer_to_staff)

    async def run(self, transport, handle_sigint=True):
        """Builds and runs the pipeline with the provided transport."""
        
        # 1. Setup Aggregators with Smart Turn Strategy
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            self.context,
            user_params=LLMUserAggregatorParams(
                user_turn_strategies=UserTurnStrategies(
                    stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=self.turn_analyzer)]
                ),
            ),
        )

        # 2. Initialize RTVI (Real-Time Voice Interface)
        rtvi = RTVIProcessor()

        # 3. Construct Pipeline
        pipeline = Pipeline([
            transport.input(),
            rtvi,              # Standardize events
            self.stt,
            user_aggregator,   # Decides when user is done
            self.llm,
            self.tts,
            transport.output(),
            assistant_aggregator, # Capture assistant output for context
        ])

        # 4. Create Task
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[RTVIObserver(rtvi)], # Allows frontend to see state
        )

        # 5. Register Event Handlers
        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("User joined. Triggering greeting...")
            # Instruct LLM to speak first
            self.messages.append({"role": "system", "content": "Say hello and ask how you can help with their order."})
            await task.queue_frames([LLMRunFrame()])

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("User disconnected.")
            await task.cancel()

        # 6. Run
        logger.info("Pipeline starting...")
        runner = PipelineRunner(handle_sigint=handle_sigint)
        await runner.run(task)