import base64
import io
import os
import tempfile
import traceback
from typing import Any

import numpy as np
import runpod
import torch
from PIL import Image, ImageOps
from diffusers import WanImageToVideoPipeline
from diffusers.utils import export_to_video

MODEL_ID = os.getenv(
    "MODEL_NAME",
    "TestOrganizationPleaseIgnore/WAMU_v3_WAN2.2_I2V_LIGHTNING",
)
FIXED_FPS = int(os.getenv("FIXED_FPS", "16"))
MAX_AREA = int(os.getenv("MAX_AREA", str(480 * 832)))
MIN_FRAMES = 9
MAX_FRAMES = 161

DEFAULT_NEGATIVE_PROMPT = (
    "overexposed, static, blurry details, subtitles, watermark, text, "
    "low quality, jpeg artifacts, deformed anatomy, extra fingers, "
    "bad hands, bad face, duplicate person, extra limbs, frozen frame"
)

_PIPELINE = None


def decode_image(value: str) -> Image.Image:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("image is required.")

    encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    raw = base64.b64decode(encoded, validate=False)
    return ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")


def normalize_num_frames(value: int) -> int:
    value = max(MIN_FRAMES, min(MAX_FRAMES, int(value)))
    # Wan temporal VAE is happiest with 4k+1 frame counts.
    k = round((value - 1) / 4)
    return max(MIN_FRAMES, min(MAX_FRAMES, 4 * k + 1))


def get_num_frames(duration: float, requested_frames: Any = None) -> int:
    if requested_frames not in (None, ""):
        return normalize_num_frames(int(requested_frames))
    return normalize_num_frames(int(round(duration * FIXED_FPS)) + 1)


def get_pipeline():
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required.")

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")

    print(f"[model] Loading Wan I2V: {MODEL_ID}", flush=True)

    pipe = WanImageToVideoPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        token=token,
        low_cpu_mem_usage=True,
    )

    # Keep the 48 GB worker viable by offloading inactive modules to CPU.
    pipe.enable_model_cpu_offload()

    if getattr(pipe, "vae", None) is not None:
        try:
            pipe.vae.enable_tiling()
        except Exception:
            pass
        try:
            pipe.vae.enable_slicing()
        except Exception:
            pass

    pipe.set_progress_bar_config(disable=False)
    _PIPELINE = pipe

    print("[model] Wan I2V ready", flush=True)
    return _PIPELINE


def resize_for_wan(image: Image.Image, pipe) -> Image.Image:
    aspect_ratio = image.height / image.width

    # Same sizing idea as the official Wan2.2 Diffusers example.
    mod_value = 16
    try:
        mod_value = (
            pipe.vae_scale_factor_spatial
            * pipe.transformer.config.patch_size[1]
        )
    except Exception:
        pass

    height = max(mod_value, round(np.sqrt(MAX_AREA * aspect_ratio)) // mod_value * mod_value)
    width = max(mod_value, round(np.sqrt(MAX_AREA / aspect_ratio)) // mod_value * mod_value)

    return image.resize((int(width), int(height)), Image.Resampling.LANCZOS)


def encode_video(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def handler(job: dict[str, Any]) -> dict[str, Any]:
    video_path = None

    try:
        print("[job] JOB RECEIVED", flush=True)
        job_input = job.get("input") or {}

        # Accept both the new I2V field name and the old frontend field name.
        image_value = job_input.get("image") or job_input.get("base_image")
        if not image_value:
            raise ValueError("image or base_image is required.")

        print("[job] IMAGE RECEIVED", flush=True)

        prompt = str(job_input.get("prompt", "")).strip()
        if len(prompt) < 3:
            raise ValueError("prompt is required.")

        duration = max(0.5, min(10.0, float(job_input.get("duration", 3.5))))
        num_frames = get_num_frames(duration, job_input.get("num_frames"))
        actual_duration = (num_frames - 1) / FIXED_FPS

        steps = max(1, min(30, int(job_input.get("steps", 4))))
        guidance_scale = max(0.0, min(20.0, float(job_input.get("guidance_scale", 1.0))))
        seed = int(job_input.get("seed", 42))
        negative_prompt = str(
            job_input.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
        )

        print("[job] MODEL LOADING", flush=True)
        pipe = get_pipeline()
        print("[job] MODEL READY", flush=True)

        image = resize_for_wan(decode_image(image_value), pipe)
        print(f"[job] IMAGE DECODED {image.width}x{image.height}", flush=True)

        print(
            f"[job] Wan I2V {image.width}x{image.height}; "
            f"frames={num_frames}; fps={FIXED_FPS}; "
            f"steps={steps}; guidance={guidance_scale}; seed={seed}",
            flush=True,
        )

        generator = torch.Generator(device="cpu").manual_seed(seed)

        print("[job] GENERATING", flush=True)

        with torch.inference_mode():
            frames = pipe(
                image=image,
                prompt=prompt,
                negative_prompt=negative_prompt,
                height=image.height,
                width=image.width,
                num_frames=num_frames,
                guidance_scale=guidance_scale,
                num_inference_steps=steps,
                generator=generator,
            ).frames[0]

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        video_path = tmp.name
        tmp.close()

        export_to_video(frames, video_path, fps=FIXED_FPS)
        video_b64 = encode_video(video_path)

        print("[job] GENERATION COMPLETE", flush=True)

        return {
            "ok": True,
            "video_base64": video_b64,
            "mime_type": "video/mp4",
            "model": MODEL_ID,
            "seed": seed,
            "steps": steps,
            "guidance_scale": guidance_scale,
            "fps": FIXED_FPS,
            "num_frames": num_frames,
            "duration": actual_duration,
            "width": image.width,
            "height": image.height,
        }

    except Exception as error:
        traceback.print_exc()
        return {
            "ok": False,
            "error": str(error),
            "error_type": type(error).__name__,
            "model": MODEL_ID,
        }

    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass


if __name__ == "__main__":
    print("[worker] WORKER STARTED — Motion Studio Wan 2.2 I2V", flush=True)
    print(f"[worker] MODEL_NAME={MODEL_ID}", flush=True)
    print(f"[worker] FPS={FIXED_FPS} MAX_AREA={MAX_AREA}", flush=True)
    runpod.serverless.start({"handler": handler})
