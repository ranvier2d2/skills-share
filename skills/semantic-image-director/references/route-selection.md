# Route Selection

## Route Selection Principle

Do not treat `imagegen` as old DALL-E-era image generation. In this environment, `imagegen` should be understood as a prompt-only wrapper over the current OpenAI ChatGPT Images / Image Gen 2 capability class. It is often capable of rich composition, short-to-medium text, visual explanation, multi-object layout, and infographic-like images.

Choose the route based on artifact contract:

- Use `imagegen` when the desired artifact is primarily a final communicational image.
- Use deterministic rendering when the artifact must be exact, editable, auditable, data-bound, clickable, or maintained as a document/UI.
- Use hybrid when visual impact and exact control are both needed.

## Use A Deterministic Renderer

Choose HTML/CSS, SVG, Figma, slides, or `intent-html-renderer` when:

- text must be exact;
- layout must match a page, deck, screenshot, or product UI;
- diagrams contain many labels, citations, data tables, or exact copy;
- the artifact will be edited later;
- the result is a product/workbench/dashboard/page;
- the output must be mechanically parseable, reusable, or auditable;
- any invented copy, icons, numbers, or labels would create unacceptable risk.

## Use Image Generation

Choose `imagegen` when:

- the result is a bitmap asset;
- the user wants a poster, visual metaphor, illustration, product mockup, concept image, explanatory visual, light diagram, or compact infographic;
- visual meaning, scene, hierarchy, texture, emotion, or composition matters;
- short-to-medium text or labels are useful and can be inspected;
- the purpose is communication, persuasion, teaching, or ideation rather than durable specification;
- the model can be pushed with explicit semantic locks, label budget, layout instructions, and negative semantics.

Do not reroute away from `imagegen` merely because the user wants text. Reroute only when exactness, editability, auditability, or long-form content is the governing requirement.

## Use Hybrid Route

Choose hybrid when:

- the page/layout/text must be deterministic, but it needs a rich visual layer;
- a presentation needs exact copy plus generated hero art;
- a UI mockup should contain generated imagery inside a stable frame.
- an `imagegen` output is semantically strong but needs exact labels, links, citations, or corrections;
- the artifact should be both emotionally memorable and operationally precise.

Recommended order:

1. Create deterministic layout.
2. Generate isolated visual layer or background.
3. Compose the two.
4. Inspect text and semantic fidelity.

## Reroute Triggers

Reroute away from `imagegen` if:

- first output literalizes a technical term;
- required text is long, wrong, or must be exact;
- the artifact is essentially a page/screen with exact copy;
- repeated generations improve aesthetics but not meaning.
