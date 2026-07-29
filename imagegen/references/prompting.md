# Prompting guidance

Adapted from the Codex imagegen skill.

## Structure

Keep prompts concise but specific:

```text
Use case: <product-mockup|photorealistic-natural|ui-mockup|illustration-story|...>
Primary request: <what you want>
Subject: <main subject>
Scene/backdrop: <environment>
Style/medium: <photo/illustration/3D/etc>
Composition/framing: <wide/close/top-down>
Lighting/mood: <lighting + mood>
Constraints: <must keep / must avoid>
Avoid: <negative constraints>
```

## Rules

- Quote exact text and specify typography, placement, and casing.
- For edits, list invariants explicitly: `change only X; keep Y unchanged`.
- For reference images, label each role in the prompt (e.g. `Image 1: style reference`, `Image 2: character to preserve`).
- Iterate with a single targeted change at a time.
- Do not add creative elements the user did not imply.

## Reference images

- Maximum 5 per call.
- Use local paths only.
- References guide style, composition, and subject; they do not perform pixel-perfect masking.

## Transparency

`gpt-image-2` does not support native transparent backgrounds. Workaround:

1. Prompt for a flat chroma-key background (e.g. `#00ff00`).
2. Generate the image.
3. Remove the key color locally with a chroma-key removal tool.

If true native transparency is required, that path needs `gpt-image-1.5` via the OpenAI Images API and an API key; ask the user before switching.
