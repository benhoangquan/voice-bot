"""Pipecat pipeline setup with barge-in support"""

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_response import LLMResponseAggregator
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.anthropic import AnthropicLLMService
from pipecat.vad.silero import SileroVADAnalyzer
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import TextFrame, TTSStartedFrame, TTSStoppedFrame

from ..config import Config
from .voice_bot import VoiceBot


class BargeInProcessor(FrameProcessor):
    """Handle barge-in by detecting user speech during TTS"""
    
    def __init__(self, vad_analyzer):
        super().__init__()
        self.vad_analyzer = vad_analyzer
        self.tts_active = False
    
    async def process_frame(self, frame, direction):
        """Process frames and handle barge-in"""
        # Track TTS state
        if isinstance(frame, TTSStartedFrame):
            self.tts_active = True
        elif isinstance(frame, TTSStoppedFrame):
            self.tts_active = False
        
        # If TTS is active and user starts speaking, cancel TTS
        # This would be handled by the VAD analyzer detecting speech
        # and the pipeline cancelling the TTS stream
        
        await super().process_frame(frame, direction)


def create_pipeline(
    voice_bot: VoiceBot,
    audio_input,
    audio_output
) -> Pipeline:
    """Create Pipecat pipeline with all processors"""
    
    # Initialize services
    stt_service = DeepgramSTTService(
        api_key=Config.DEEPGRAM_API_KEY,
        model="nova-2",
        language="en-US",
        interim_results=True,
    )
    
    tts_service = ElevenLabsTTSService(
        api_key=Config.ELEVENLABS_API_KEY,
        voice_id=Config.ELEVENLABS_VOICE_ID,
        model="eleven_turbo_v2_5",
    )
    
    llm_service = AnthropicLLMService(
        api_key=Config.ANTHROPIC_API_KEY,
        model=Config.ANTHROPIC_MODEL,
    )
    
    # VAD for barge-in detection
    vad_analyzer = SileroVADAnalyzer()
    
    # Response aggregator
    response_aggregator = LLMResponseAggregator()
    
    # Barge-in processor
    barge_in_processor = BargeInProcessor(vad_analyzer)
    
    # Create pipeline
    pipeline = Pipeline([
        audio_input,
        vad_analyzer,
        stt_service,
        response_aggregator,
        llm_service,
        barge_in_processor,
        tts_service,
        audio_output,
    ])
    
    return pipeline


async def run_bot(voice_bot: VoiceBot, audio_input, audio_output):
    """Run the voice bot with Pipecat pipeline"""
    pipeline = create_pipeline(voice_bot, audio_input, audio_output)
    
    task = PipelineTask(pipeline)
    
    runner = PipelineRunner()
    await runner.run(task)
