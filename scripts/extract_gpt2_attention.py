"""Extract real GPT-2 attention for plotting with the attention_arcs generator.

Runs a sentence through HuggingFace gpt2 (CPU) and saves the full attention
stack to an .npz that `promptplot art attention_arcs --param attn_npz=...`
consumes. Keeps torch/transformers out of the generator itself.

Usage:
    python3 scripts/extract_gpt2_attention.py --text "..." --out ~/.promptplot/attn_gpt2.npz
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--text",
        default="The pen plotter drew a black hole while the transformer watched itself think.",
    )
    ap.add_argument("--model", default="gpt2")
    ap.add_argument("--out", default=os.path.expanduser("~/.promptplot/attn_gpt2.npz"))
    args = ap.parse_args()

    import numpy as np
    import torch
    from transformers import GPT2LMHeadModel, GPT2TokenizerFast

    tok = GPT2TokenizerFast.from_pretrained(args.model)
    model = GPT2LMHeadModel.from_pretrained(args.model, output_attentions=True)
    model.eval()

    enc = tok(args.text, return_tensors="pt")
    with torch.no_grad():
        out = model(**enc)
    # (layers, heads, T, T)
    attn = torch.stack(out.attentions, dim=0).squeeze(1).numpy()
    tokens = [tok.decode([t]) for t in enc["input_ids"][0]]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    np.savez_compressed(args.out, attn=attn.astype(np.float32))
    print(f"model={args.model} layers={attn.shape[0]} heads={attn.shape[1]} tokens={attn.shape[2]}")
    print("tokens:", tokens)
    print("saved:", args.out)


if __name__ == "__main__":
    main()
