"""Local audio transport adapter for microphone and speaker input/output"""

from typing import Optional
import asyncio
import pyaudio
from pipecat.transports.local.audio import (
    LocalAudioInputTransport,
    LocalAudioOutputTransport,
    LocalAudioTransportParams
)


class LocalAudioTransport:
    """Transport adapter for local microphone and speaker using Pipecat"""
    
    def __init__(
        self,
        input_device_index: Optional[int] = None,
        output_device_index: Optional[int] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        frames_per_buffer: int = 320  # 20ms at 16kHz
    ):
        """
        Initialize local audio transport
        
        Args:
            input_device_index: PyAudio device index for microphone (None = default)
            output_device_index: PyAudio device index for speaker (None = default)
            sample_rate: Audio sample rate (default: 16000 Hz)
            channels: Number of audio channels (default: 1 for mono)
            frames_per_buffer: Frames per buffer (default: 320 = 20ms at 16kHz)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer
        
        # Initialize PyAudio
        self.py_audio = pyaudio.PyAudio()
        
        # Create transport parameters
        # Note: audio_in_enabled and audio_out_enabled might be needed depending on Pipecat version
        params = LocalAudioTransportParams(
            input_device_index=input_device_index,
            output_device_index=output_device_index,
            audio_in_sample_rate=sample_rate,
            audio_in_channels=channels,
            audio_out_sample_rate=sample_rate,
            audio_out_channels=channels
        )
        
        # Try to set enabled flags if the params object supports them
        try:
            if hasattr(params, 'audio_in_enabled'):
                params.audio_in_enabled = True
            if hasattr(params, 'audio_out_enabled'):
                params.audio_out_enabled = True
        except:
            pass  # Some versions might not have these attributes
        
        # Create input and output transports
        self.input_transport = LocalAudioInputTransport(
            py_audio=self.py_audio,
            params=params
        )
        
        self.output_transport = LocalAudioOutputTransport(
            py_audio=self.py_audio,
            params=params
        )
    
    def input(self):
        """Return the input frame processor (microphone)"""
        return self.input_transport
    
    def output(self):
        """Return the output frame processor (speaker)"""
        return self.output_transport
    
    async def cleanup(self):
        """Clean up audio resources"""
        if hasattr(self, 'input_transport'):
            if hasattr(self.input_transport, 'cleanup'):
                cleanup_method = self.input_transport.cleanup
                if asyncio.iscoroutinefunction(cleanup_method):
                    await cleanup_method()
                else:
                    cleanup_method()
        if hasattr(self, 'output_transport'):
            if hasattr(self.output_transport, 'cleanup'):
                cleanup_method = self.output_transport.cleanup
                if asyncio.iscoroutinefunction(cleanup_method):
                    await cleanup_method()
                else:
                    cleanup_method()
        if hasattr(self, 'py_audio'):
            self.py_audio.terminate()
    
    @staticmethod
    def list_audio_devices():
        """List available audio input and output devices"""
        p = pyaudio.PyAudio()
        devices = []
        
        print("\n=== Available Audio Devices ===\n")
        print(f"{'Index':<8} {'Name':<40} {'Input':<8} {'Output':<8} {'Sample Rate':<12}")
        print("-" * 80)
        
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            devices.append({
                'index': i,
                'name': info['name'],
                'max_input_channels': info['maxInputChannels'],
                'max_output_channels': info['maxOutputChannels'],
                'default_sample_rate': info['defaultSampleRate']
            })
            
            print(
                f"{i:<8} "
                f"{info['name']:<40} "
                f"{'Yes' if info['maxInputChannels'] > 0 else 'No':<8} "
                f"{'Yes' if info['maxOutputChannels'] > 0 else 'No':<8} "
                f"{int(info['defaultSampleRate']):<12}"
            )
        
        print("\n" + "=" * 80 + "\n")
        p.terminate()
        return devices
