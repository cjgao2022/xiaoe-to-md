"""
用 faster-whisper 把 mp4/mp3 转录为带时间戳的文本段列表。
"""

import os
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def transcribe(audio_path: Path, model_size: str = "small", language: str = "zh",
               on_segment=None) -> list[dict]:
    """
    转录音频文件，返回 [{'start': float, 'end': float, 'text': str}, ...]
    on_segment(seg_dict, progress_pct): 可选回调，每段转录完后调用
    """
    from faster_whisper import WhisperModel

    print(f"加载 Whisper 模型 ({model_size})，首次运行会下载模型...", flush=True)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"开始转录: {audio_path.name}", flush=True)
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    duration = info.duration
    print(f"检测语言: {info.language}，时长: {duration:.1f}s", flush=True)

    result = []
    for seg in segments:
        item = {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
        result.append(item)
        pct = (seg.start / duration * 100) if duration > 0 else 0
        m, s = int(seg.start // 60), seg.start % 60
        print(f"  [{m:02d}:{s:05.2f}] {seg.text.strip()}", flush=True)
        if on_segment:
            on_segment(item, pct)

    print(f"转录完成，共 {len(result)} 段", flush=True)
    return result
