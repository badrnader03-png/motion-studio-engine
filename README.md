# Motion Studio Qwen Engine

RunPod Serverless worker for Qwen Image Edit 2511.

## Cached model

Set the RunPod endpoint **Model** field to:

```text
Qwen/Qwen-Image-Edit-2511
```

## Input

Images must be base64 strings or data URLs.

```json
{
  "input": {
    "base_image": "data:image/jpeg;base64,...",
    "reference_image": "data:image/jpeg;base64,...",
    "prompt": "Keep the identity from image 1 and transfer the outfit and background from image 2.",
    "steps": 20,
    "seed": 0,
    "true_cfg_scale": 4.0,
    "negative_prompt": "blurry, distorted face, duplicate person"
  }
}
```

## Output

```json
{
  "ok": true,
  "image_base64": "...",
  "mime_type": "image/png"
}
```

## Hardware note

Qwen Image Edit 2511 is a 20B BF16 model. This worker uses CPU offload and 768px input limits to attempt operation on a 24 GB GPU. It will be slower than running on a 48 GB or larger GPU and may still require a larger GPU depending on the host's available system RAM and the requested image dimensions.
