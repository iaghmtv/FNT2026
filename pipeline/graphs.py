# -*- coding: utf-8 -*-
"""Grafos de ComfyUI (formato API) usados por el pipeline FNT 2026."""

FLUX_UNET = "flux1-krea-dev_fp8_scaled.safetensors"
FLUX_DEPTH_LORA = "flux1-depth-dev-lora.safetensors"
QWEN_UNET = "qwen_image_edit_2511_fp8mixed.safetensors"
QWEN_LORA = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
H3_UNET = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
H3_LORA = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"


def _flux_base(prompt, guidance):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": FLUX_UNET, "weight_dtype": "default"}},
        "3": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "clip_l.safetensors", "clip_name2": "t5xxl_fp8_e4m3fn_scaled.safetensors", "type": "flux"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt}},
        "6": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": guidance}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": ""}},
    }


def flux_depth(depth_name, prompt, w, h, seed, prefix, steps=24, guidance=10.0, lora=1.0):
    """Flux Krea + LoRA de profundidad: el relieve del Z-depth define la forma del paisaje."""
    g = _flux_base(prompt, guidance)
    g.update({
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": FLUX_DEPTH_LORA, "strength_model": lora}},
        "8": {"class_type": "LoadImage", "inputs": {"image": depth_name}},
        "9": {"class_type": "ImageScale", "inputs": {"image": ["8", 0], "upscale_method": "lanczos", "width": w, "height": h, "crop": "disabled"}},
        "10": {"class_type": "InstructPixToPixConditioning", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "vae": ["4", 0], "pixels": ["9", 0]}},
        "11": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": ["10", 0], "negative": ["10", 1], "latent_image": ["10", 2],
                                                    "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": prefix}},
    })
    return g


def flux_t2i(prompt, w, h, seed, prefix, steps=26, guidance=3.5):
    """Flux Krea texto a imagen (pantallas centrales)."""
    g = _flux_base(prompt, guidance)
    g.update({
        "8": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "11": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["8", 0],
                                                    "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["4", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": prefix}},
    })
    return g


def qwen_edit(image_names, prompt, seed, prefix, megapixels=1.0):
    """Qwen Image Edit 2511 + Lightning 4 pasos. image_names[0] es la imagen a editar; las demás son referencias.
    La salida conserva la proporción de image_names[0] (escalada a ~1 MP)."""
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": QWEN_UNET, "weight_dtype": "default"}},
        "2": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.1}},
        "3": {"class_type": "CFGNorm", "inputs": {"model": ["2", 0], "strength": 1.0}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["3", 0], "lora_name": QWEN_LORA, "strength_model": 1.0}},
        "5": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
    }
    pos = {"clip": ["5", 0], "vae": ["6", 0], "prompt": prompt}
    neg = {"clip": ["5", 0], "vae": ["6", 0], "prompt": ""}
    for i, name in enumerate(image_names[:3]):
        li = str(20 + i)
        g[li] = {"class_type": "LoadImage", "inputs": {"image": name}}
        src = [li, 0]
        if i == 0:
            g["30"] = {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": [li, 0], "upscale_method": "lanczos", "megapixels": megapixels, "resolution_steps": 16}}
            src = ["30", 0]
        pos[f"image{i + 1}"] = src
        neg[f"image{i + 1}"] = src
    g.update({
        "9": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": pos},
        "10": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": neg},
        "11": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["9", 0], "reference_latents_method": "index_timestep_zero"}},
        "12": {"class_type": "FluxKontextMultiReferenceLatentMethod", "inputs": {"conditioning": ["10", 0], "reference_latents_method": "index_timestep_zero"}},
        "13": {"class_type": "VAEEncode", "inputs": {"pixels": ["30", 0], "vae": ["6", 0]}},
        "14": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["11", 0], "negative": ["12", 0], "latent_image": ["13", 0],
                                                    "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["6", 0]}},
        "16": {"class_type": "SaveImage", "inputs": {"images": ["15", 0], "filename_prefix": prefix}},
    })
    return g


def h3_timelapse(first, last, guides, prompt, w, h, length, seed, prefix):
    """MiniMax H3 primer/último cuadro + cuadros guía intermedios (noche -> amanecer -> mediodía -> atardecer -> noche).
    guides: lista de (nombre_imagen, frame_idx). length = 17k+5 (141, 175, 209, 243...)."""
    cond = "9"
    g = {}
    for n, (name, fi) in enumerate(guides):
        li, gi = str(30 + 2 * n), str(31 + 2 * n)
        g[li] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[gi] = {"class_type": "MiniMaxH3AddGuide", "inputs": {"positive": [cond, 0], "latent": ["9", 1], "frame_idx": fi, "vae": ["4", 0], "image": [li, 0]}}
        cond = gi
    g.update({
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": H3_UNET, "weight_dtype": "default"}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": H3_LORA, "strength_model": 1.0}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "6": {"class_type": "LoadImage", "inputs": {"image": first}},
        "7": {"class_type": "LoadImage", "inputs": {"image": last}},
        "9": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["3", 0], "vae": ["4", 0], "prompt": prompt, "width": w, "height": h,
                                                               "length": length, "first_frame": ["6", 0], "last_frame": ["7", 0]}},
        "11": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "12": {"class_type": "BasicScheduler", "inputs": {"model": ["2", 0], "scheduler": "simple", "steps": 8, "denoise": 1.0}},
        "13": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "14": {"class_type": "BasicGuider", "inputs": {"model": ["2", 0], "conditioning": [cond, 0]}},
        "15": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["13", 0], "guider": ["14", 0], "sampler": ["11", 0], "sigmas": ["12", 0], "latent_image": ["9", 1]}},
        "16": {"class_type": "VAEDecode", "inputs": {"samples": ["15", 0], "vae": ["4", 0]}},
        "18": {"class_type": "CreateVideo", "inputs": {"images": ["16", 0], "fps": 24.0}},
        "19": {"class_type": "SaveVideo", "inputs": {"video": ["18", 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}},
    })
    return g
