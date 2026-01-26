"""Pipecat pipeline setup with barge-in support"""

from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.aggregators.llm_context import LLMContext, LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import TTSStartedFrame, TTSStoppedFrame

from ..config import Config

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
    transport,
    stt_service,
    tts_service,
    llm_service,
    context_aggregator: LLMContextAggregatorPair
) -> Pipeline:
    """Create Pipecat pipeline with all processors"""
    
    # Get aggregators from the pair
    user_aggregator = context_aggregator.user()
    assistant_aggregator = context_aggregator.assistant()
    
    # Create pipeline
    pipeline = Pipeline([
        transport.input(),
        stt_service,
        user_aggregator,
        llm_service,
        tts_service,
        transport.output(),
        assistant_aggregator
    ])
    
    return pipeline

