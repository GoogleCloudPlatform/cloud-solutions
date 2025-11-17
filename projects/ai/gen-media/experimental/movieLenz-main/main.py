# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Main entry point for movieLenz video evaluation and prompt optimization.

This script provides a command-line interface for:
- Evaluating videos
- Creating optimized prompts
- Optimizing prompts based on video feedback
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import prompt_optimizer_main
import runner
from absl import flags

# Initialize absl flags for prompt_optimizer_main
# This is required because prompt_optimizer_main uses absl flags internally
if not flags.FLAGS.is_parsed():
    flags.FLAGS(sys.argv[:1])  # Parse with empty args to initialize


def setup_logging(verbose: bool = False):
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def validate_file_path(file_path: str, file_type: str) -> str:
    """Validate that a file exists and is readable."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"{file_type} file not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"{file_type} path is not a file: {file_path}")
    return str(path.absolute())


def handle_evaluate(args, logger):
    """Handle video evaluation mode."""
    # Validate required inputs for evaluation
    if not args.video_path:
        raise ValueError("--video-path is required for evaluate mode")
    if not args.image_path:
        raise ValueError("--image-path is required for evaluate mode")
    if not args.query:
        raise ValueError("--query is required for evaluate mode")

    # Validate file paths
    video_path = validate_file_path(args.video_path, "Video")
    image_path = validate_file_path(args.image_path, "Image")

    logger.info("Starting video evaluation...")
    logger.info("Video: %s", video_path)
    logger.info("Image: %s", image_path)
    logger.info("Query: %s", args.query)
    logger.info("Duration: %ds", args.duration)

    # Run the evaluation
    results = runner.run_evaluate_media_for_video_path(
        video_query=args.query,
        video_path=video_path,
        input_image_path=image_path,
        duration=args.duration,
        dsg_questions=args.dsg_questions,
        common_mistake_questions=args.cmq_questions,
    )

    logger.info("Evaluation completed successfully!")
    return results


def handle_create(args, logger):
    """Handle prompt creation/optimization mode."""
    if not args.prompt:
        raise ValueError("--prompt is required for create mode")

    logger.info("Creating optimized prompt...")
    logger.info("Initial prompt: %s", args.prompt)
    if args.start_frame:
        logger.info("Start frame: %s", args.start_frame)
    if args.end_frame:
        logger.info("End frame: %s", args.end_frame)

    # Validate optional file paths
    start_frame = (
        validate_file_path(args.start_frame, "Start frame")
        if args.start_frame
        else None
    )
    end_frame = (
        validate_file_path(args.end_frame, "End frame")
        if args.end_frame
        else None
    )

    # Run prompt optimization
    optimized_prompt = prompt_optimizer_main.runner_single_run(
        initial_prompt=args.prompt,
        start_frame_path=start_frame,
        end_frame_path=end_frame,
        video_duration=args.duration if args.duration != 8 else None,
        technical_notes=args.technical_notes,
    )

    logger.info("Prompt optimization completed!")

    # Return as structured result
    return {
        "original_prompt": args.prompt,
        "optimized_prompt": optimized_prompt,
        "duration": args.duration,
        "technical_notes": args.technical_notes,
    }


def handle_optimize(args, logger):
    """Handle iterative prompt optimization with video feedback mode."""
    if not args.prompt:
        raise ValueError("--prompt is required for optimize mode")
    if not args.video_path:
        raise ValueError("--video-path is required for optimize mode")

    logger.info("Optimizing prompt with video feedback...")
    logger.info("Initial prompt: %s", args.prompt)
    logger.info("Video: %s", args.video_path)

    # Validate file paths
    video_path = validate_file_path(args.video_path, "Video")
    start_frame = (
        validate_file_path(args.start_frame, "Start frame")
        if args.start_frame
        else None
    )
    end_frame = (
        validate_file_path(args.end_frame, "End frame")
        if args.end_frame
        else None
    )

    # Run iterative optimization
    result = prompt_optimizer_main.runner_optimization(
        initial_prompt=args.prompt,
        start_frame_path=start_frame,
        end_frame_path=end_frame,
        video_duration=args.duration if args.duration != 8 else None,
        technical_notes=args.technical_notes,
        video_path=video_path,
    )

    logger.info("Iterative optimization completed!")
    return {"result": result}


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="MovieLenz: Video evaluation and prompt optimization tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate a video
  python main.py evaluate --query "An old man cleaning lawn" \\
    --video-path video.mp4 --image-path start_frame.png

  # Create optimized prompt
  python main.py create --prompt "A person running" \\
    --start-frame start.png --duration 10

  # Optimize prompt with video feedback
  python main.py optimize --prompt "Dancing" \\
    --video-path dance.mp4 --start-frame start.png
        """,
    )

    # Add mode selection
    subparsers = parser.add_subparsers(
        dest="mode", help="Operation mode", required=True
    )

    # ========== EVALUATE MODE ==========
    eval_parser = subparsers.add_parser(
        "evaluate",
        help="Evaluate a video against a query",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py evaluate --query "Running" --video-path run.mp4 --image-path start.png
  python main.py evaluate --query "Cooking" --video-path cook.mp4 --image-path chef.png --output results.json --pretty
        """,
    )
    eval_parser.add_argument(
        "--query", "-q", type=str, required=True, help="Video query/description"
    )
    eval_parser.add_argument(
        "--video-path",
        "-v",
        type=str,
        required=True,
        help="Path to the video file",
    )
    eval_parser.add_argument(
        "--image-path",
        "-i",
        type=str,
        required=True,
        help="Path to the input image file",
    )
    eval_parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=8,
        help="Video duration in seconds (default: 8)",
    )
    eval_parser.add_argument(
        "--dsg-questions", type=str, help="DSG questions (JSON string)"
    )
    eval_parser.add_argument(
        "--cmq-questions",
        type=str,
        help="Common Mistake Questions (JSON string)",
    )

    # ========== CREATE MODE ==========
    create_parser = subparsers.add_parser(
        "create",
        help="Create an optimized prompt for video generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py create --prompt "A person running in a park"
  python main.py create --prompt "Dancing" --start-frame start.png --duration 10
  python main.py create --prompt "Cooking" --technical-notes "Professional kitchen, bright lighting"
        """,
    )
    create_parser.add_argument(
        "--prompt",
        "-p",
        type=str,
        required=True,
        help="Initial prompt to optimize",
    )
    create_parser.add_argument(
        "--start-frame", type=str, help="Path to start frame image (optional)"
    )
    create_parser.add_argument(
        "--end-frame", type=str, help="Path to end frame image (optional)"
    )
    create_parser.add_argument(
        "--duration", "-d", type=int, help="Target video duration in seconds"
    )
    create_parser.add_argument(
        "--technical-notes", type=str, help="Technical notes or creative brief"
    )

    # ========== OPTIMIZE MODE ==========
    optimize_parser = subparsers.add_parser(
        "optimize",
        help="Optimize prompt iteratively with video feedback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py optimize --prompt "Running" --video-path run.mp4 --start-frame start.png
  python main.py optimize --prompt "Dancing" --video-path dance.mp4 --duration 10
        """,
    )
    optimize_parser.add_argument(
        "--prompt",
        "-p",
        type=str,
        required=True,
        help="Initial prompt to optimize",
    )
    optimize_parser.add_argument(
        "--video-path",
        "-v",
        type=str,
        required=True,
        help="Path to the video file for feedback",
    )
    optimize_parser.add_argument(
        "--start-frame", type=str, help="Path to start frame image (optional)"
    )
    optimize_parser.add_argument(
        "--end-frame", type=str, help="Path to end frame image (optional)"
    )
    optimize_parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=8,
        help="Video duration in seconds (default: 8)",
    )
    optimize_parser.add_argument(
        "--technical-notes", type=str, help="Technical notes or creative brief"
    )

    # ========== COMMON OPTIONS ==========
    for subparser in [eval_parser, create_parser, optimize_parser]:
        subparser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Output file path to save results as JSON",
        )
        subparser.add_argument(
            "--verbose", action="store_true", help="Enable verbose logging"
        )
        subparser.add_argument(
            "--pretty", action="store_true", help="Pretty print JSON output"
        )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    results = None
    try:
        # Route to appropriate handler based on mode
        if args.mode == "evaluate":
            results = handle_evaluate(args, logger)
        elif args.mode == "create":
            results = handle_create(args, logger)
        elif args.mode == "optimize":
            results = handle_optimize(args, logger)
        else:
            parser.error(f"Unknown mode: {args.mode}")

        # Format output
        if isinstance(results, dict):
            if args.pretty:
                output = json.dumps(results, indent=2, sort_keys=True)
            else:
                output = json.dumps(results)
        else:
            output = str(results)

        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(output, encoding="utf-8")
            logger.info("Results saved to: %s", args.output)
            print(f"Results saved to: {args.output}")
        else:
            # Print to stdout
            print("\nResults:")
            print(output)

        return 0

    except FileNotFoundError as e:
        logger.error("File error: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        logger.error("Validation error: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, KeyError) as e:
        logger.exception("Unexpected error: %s", e)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
