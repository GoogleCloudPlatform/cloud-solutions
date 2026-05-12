# Generative Media Shot Production Demo

Welcome to the Generative Media Shot Production Demo. In this demo, we will
leverage Google's Generative Media models to create digital content for
different stages in shot production. The demo will use ComfyUI as an interface
to access the Google's Generative media models via Gemini Enterprise Agent
Platform(formerly known as Vertex AI) APIs. The same steps can be replicated
with an interface of your choice e.g
[Creative Studio](https://github.com/GoogleCloudPlatform/gcc-creative-studio),
[Flow](https://labs.google/fx/tools/flow) etc. Please see the terms and
conditions for these tools before using them.

## Google Generative Media models

Google offers Generative Media models like **Veo**, **Nano Banana**, **Gemini**
and **Lyria**. All of Google’s models offer SOTA(State-of-the-art) security,
enterprise data silo protection and end user indemnity. We ensure your data
remains private and is never used to train our foundation models without your
permission. We offer a two-pronged indemnity approach covering both training
data and generated output to help you innovate responsibly.

### Nano Banana

Nano Banana allows complete creative control of creation of images. It provides
subject consistency by letting you maintain character resemblance of up to five
characters and the fidelity of up to 14 objects in a single workflow, allowing
you to storyboard and build narratives without altering the appearance of your
inputs.
[Prompting best practices](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana?e=48754805)
make it easy to control every aspect of an image. Features like
Reference-to-Image allows users to control the models using traditional
techniques, making them an extension of their creative workflow. It also offers
Production-ready resolutions from 512px to 4K. Check out
[Nano Banan documentation](https://ai.google.dev/gemini-api/docs/image-generation)
for more dtails.

### Veo

Veo allows complete creative control of creation of videos. With Image-to-Video,
you can animate a specific starting frame or define the exact path of motion by
providing both first and last frames. Additionally, Reference-to-Video enables
you to guide the model's aesthetic output by transferring styles and textures
from your source imagery to the final render. It supports Production-ready 720P,
1080P and 4K resolutions.
[Prompting best practices](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1?e=48754805)
provides more control over the video creation. Veo’s Extend Video feature acts
as a "keep going" button, seamlessly lengthening your clips while maintaining
perfect visual consistency. Check out
[Veo documentation](https://ai.google.dev/gemini-api/docs/video?example=dialogue)
for more details.

### Lyria

Lyria allows complete creative control of creation of music. It supports
professional-grade composition where doesn't just loop; it understands musical
structure (intros, verses, choruses, and bridges) for tracks. It support
high-fidelity vocals, from soulful baritones to clear sopranos, to multilingual
lyrics (8+ languages). You can dial in specific BPM, instruments, and dynamics,
giving the creator the "director's chair" rather than just a "generate" button.
It provides a solution to the "overused track" problem by generating unique,
signature sonic identities that don't exist anywhere else. Checkout
[Prompting best practices](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-lyria-3-pro?e=48754805)
for Lyria to generate music with more control. For more details checkout
[Lyria documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-reference/lyria-music-generation).

## Prerequisite

In order to run this guide, you need to accomplish these prerequisites:

- You have a ComfyUI instance up and running. We highly recommend that you use a
  secure ComfyUI instance that is not exposed to the internet. If you are
  looking to run ComfyUI in a secure way on Google Cloud, please follow this
  [guide](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/main/platforms/gke/base/use-cases/inference-ref-arch/examples/comfyui).
- You are familiar with ComfyUI interface and how workflows can be stitched
  together to create digital content.
- You can download custom nodes either through ComfyUI manager or manually.
- You have a GCP project with Gemini Enterprise Agent Platform APIs enabled.
- You have `aiplatform.user` role on the project if you want to run the custom
  nodes with your Google Cloud userid.

## Pricing

This section provides information on the cost incurred in addition to any cost
incurred by your choice of tool/interface to run the demo e.g ComfyUI. You will
use Google GenMdeia ComfyUI custom nodes in this demo which use Gemini
Enterprise Agent Platform(formerly known as Vertex AI) APIs to generate content
and hence,
[Gemini Enterprise Agent Platform Pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
is applied to each API call. See the pricing for the model that you want to use.

Note : If you store the content in Google Cloud Storage using these custom
nodes, refer to
[Google Cloud Storage pricing](https://cloud.google.com/storage/pricing?e=48754805&hl=en).

## Demo structure

This demo contains the following guides:

This [README.md](./README.md) that gives an introduction of the demo,
prerequisites, demo structure and Google Generative media models you will use
for the demo.

[DEPLOYMENT.md](./DEPLOYMENT.md) that shows how to install the required
dependencies including custom nodes to run the demo.

[USER_GUIDE.md](./USER_GUIDE.md) that serves as the main guide to run the demo.
This guide links out to other guides that deomstrate different phases of the
demo:

- [CASTING.md](./CASTING.md)
- [CHARACTER_CONTINUITY.md](./CHARACTER_CONTINUITY.md)
- [ENVIRONMENT_AND_PROPS.md](./ENVIRONMENT_AND_PROPS.md)
- [STORYBOARD.md](./STORYBOARD.md)
- [SHOT_PRODUCTION.md](./SHOT_PRODUCTION.md)

The right sequence to follow is [README.md](./README.md) >
[DEPLOYMENT.md](./DEPLOYMENT.md) > [USER_GUIDE.md](./USER_GUIDE.md)

## Deployment

Follow the [deployment guide](./DEPLOYMENT.md) to download Google Generative
Media custom nodes in your ComfyUI instance.

## User Guide for Shot production

Follow the [user guide](./USER_GUIDE.md) to walk through the demo.
