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

"""Metrics module for video quality assessment."""

import math
import os
from typing import Any, Dict, List, Tuple

import cv2
import imagehash
import numpy as np
from absl import flags, logging
from matplotlib import pyplot as plt
from PIL import Image

# Local imports
from . import utils

_OUTPUT_DIR = flags.DEFINE_string(
    "output_dir",
    "DEFAULT_LOCATION",
    "Directory to output the result.",
)


class Metrics:
    """Base class for different metrics used to process series of frames."""

    def _get_stats_summary(self, data):
        """Summarizes data."""

        mean_score = np.mean(data)
        median_score = np.median(data)
        std_dev = np.std(data, ddof=1)
        variance = np.var(data, ddof=1)
        percentiles = np.percentile(data, [25, 50, 75, 90])
        stats_summary = {
            "NumSample": len(data),
            "NumSamplesWithShotChanges": np.count_nonzero(np.array(data) > 0),
            "Mean": mean_score,
            "Median": median_score,
            "Standard Deviation": std_dev,
            "Variance": variance,
            "25th Percentile": percentiles[0],
            "50th Percentile (Median)": percentiles[1],
            "75th Percentile": percentiles[2],
            "90th Percentile": percentiles[3],
        }
        return stats_summary

    def _save_histogram(self, data, num_bins: int = 10, label: str = "label"):
        """Plot data histogram and save to output directory."""

        if not os.path.exists(_OUTPUT_DIR.value):
            os.mkdir(_OUTPUT_DIR.value)
        plt.hist(data, bins=num_bins, edgecolor="black")
        plt.xlabel("Bucket")
        plt.ylabel("Count")
        plt.title(f"{label} Histogram")
        with open(
            f"{_OUTPUT_DIR.value}/{label}_histplot.png", "w", encoding="utf-8"
        ) as f:
            plt.savefig(f, format="png")
        plt.close()

    def process(
        self,
        series: List[Tuple[str, str]],
        label: str = "label",
        text_prompt: str = "",
    ) -> List[Tuple[str, Any]]:
        """Processes series of frames and returns a dictionary with
        results.

        Args:
            series: A list of tuples where each tuple contains text and
                filepath.
            label: Eval label assigned to the series.
            text_prompt: The text prompt for generation.

        Returns:
            A list of shot change counts for each video in the series.
        """
        raise NotImplementedError(
            "This method should be overridden in derived classes"
        )


class ShotChange(Metrics):
    """Derived class for the 'shot change' metric."""

    def __init__(
        self, hist: float = 0.3, ecr: float = 0.4, mse: float = 1000.0
    ):
        self._hist_threshold = hist
        self._ecr_threshold = ecr
        self._mse_threshold = mse

    def _calculate_histogram_diff(self, hist1, hist2):
        """ "calculates histogram diff."""
        return cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)

    def _calculate_edge_change_ratio(self, edges1, edges2):
        """ "calculates edge change ratio."""
        edges1_count = np.count_nonzero(edges1)
        edges2_count = np.count_nonzero(edges2)
        edge_change = np.abs(edges1_count - edges2_count) / max(
            edges1_count, edges2_count, 0.01
        )
        return edge_change

    def _calculate_mse(self, frame1, frame2):
        """ "calculates mse for two frames."""
        return np.mean((frame1 - frame2) ** 2)

    def _detect_shot_changes(self, video_path):
        """ "detects shot changes."""
        with utils.LocalCopy(video_path) as local_vid:
            cap = cv2.VideoCapture(local_vid)

        if not cap.isOpened():
            print("Error: Could not open video.")
            return None, None

        ret, prev_frame = cap.read()
        if not ret:
            print("Error: Could not read the first frame.")
            return None, None

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        prev_edges = cv2.Canny(prev_gray, 50, 150)
        prev_hist = cv2.calcHist(
            [prev_frame],
            [0, 1, 2],
            None,
            [8, 8, 8],
            [0, 256, 0, 256, 0, 256],
        )
        cv2.normalize(prev_hist, prev_hist)

        shot_changes = []
        shot_change_frame_num = []
        frame_num = 0
        while True:
            ret, curr_frame = cap.read()
            if not ret:
                break

            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
            curr_edges = cv2.Canny(curr_gray, 50, 150)
            curr_hist = cv2.calcHist(
                [curr_frame],
                [0, 1, 2],
                None,
                [8, 8, 8],
                [0, 256, 0, 256, 0, 256],
            )
            cv2.normalize(curr_hist, curr_hist)

            hist_diff = self._calculate_histogram_diff(prev_hist, curr_hist)
            ecr = self._calculate_edge_change_ratio(prev_edges, curr_edges)
            mse = self._calculate_mse(prev_gray, curr_gray)

            if (
                hist_diff > self._hist_threshold
                or ecr > self._ecr_threshold
                or mse > self._mse_threshold
            ):
                shot_changes.append(
                    math.floor(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
                )
                shot_change_frame_num.append(frame_num)

            prev_gray = curr_gray
            prev_edges = curr_edges
            prev_hist = curr_hist
            frame_num += 1

        cap.release()

        return shot_changes, shot_change_frame_num

    def process(
        self,
        series: List[Tuple[str, str]],
        label: str = "label",
        text_prompt: str = "",
    ) -> List[Tuple[str, Any]]:
        scores = []
        all_shot_changes = []
        for _, video_path in series:
            if not os.path.exists(video_path):
                logging.info(
                    "Video not found at the following path: %s",
                    video_path,
                )
                continue

            try:
                shot_changes, _ = self._detect_shot_changes(video_path)
                if shot_changes is None:
                    score = []
                else:
                    score = len(shot_changes)
                scores.append((video_path, score))
                if shot_changes is not None:
                    all_shot_changes = all_shot_changes + shot_changes
            except ValueError:
                continue

        # self._save_histogram(all_shot_changes, 6, label)
        return scores

    def process_single_video(self, video_path: str) -> Tuple[Any, Any]:
        """Process a single video and return the shot change score."""
        try:
            shot_changes, list_of_frames = self._detect_shot_changes(video_path)
            if shot_changes is not None:
                score = len(shot_changes)
                return score, list_of_frames
            return None, None
        except ValueError as e:
            logging.exception("Error processing video %s: %s", video_path, e)
            return None, None


class Blurriness(Metrics):
    """Derived class for the 'blurriness' metric using Laplacian variance."""

    def __init__(self, threshold: float = 100.0):
        """Initializes the Blurriness metric.

        Args:
            threshold: A threshold for Laplacian variance. Frames below this
                might be considered blurry. (Note: This threshold isn't
                strictly used in the average calculation below but could be
                used for other analyses).
        """
        self._threshold = threshold

    def _calculate_laplacian_variance(self, image: np.ndarray) -> float:
        """Calculates the variance of the Laplacian for a single image."""
        if image is None:
            return 0.0
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Compute the Laplacian and then the variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return laplacian_var

    def process(
        self,
        series: List[Tuple[str, str]],
        label: str = "label",
        text_prompt: str = "",
    ) -> List[Tuple[str, float]]:
        """Processes videos to calculate average blurriness.

        Args:
            series: A list of tuples where each tuple contains text and video
                filepath.
            label: Eval label assigned to the series.
            text_prompt: The text prompt used for generation (not used in
                this metric).

        Returns:
            A list of tuples, each containing the video path and its average
            Laplacian variance score. Lower scores indicate more blurriness.
        """
        video_average_scores = []
        all_frame_scores = (
            []
        )  # Optional: Collect scores from all frames across videos

        for _, video_path in series:
            if not os.path.exists(video_path):
                logging.warning("Video not found; skipping: %s", video_path)
                continue

            frame_scores = []
            try:
                with utils.LocalCopy(video_path) as local_vid:
                    cap = cv2.VideoCapture(local_vid)
                    if not cap.isOpened():
                        logging.error(
                            "Error: Could not open video: %s", video_path
                        )
                        continue

                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            break  # End of video
                        variance = self._calculate_laplacian_variance(frame)
                        frame_scores.append(variance)
                    cap.release()

            except (cv2.error, FileNotFoundError) as e:
                logging.exception(
                    "Error processing video %s: %s", video_path, e
                )
                continue  # Skip to next video

            if frame_scores:
                average_score = np.mean(frame_scores)
                video_average_scores.append((video_path, average_score))
                all_frame_scores.extend(frame_scores)  # Optional
            else:
                logging.warning("No frames processed for video: %s", video_path)
                video_average_scores.append(
                    (video_path, 0.0)
                )  # Or handle as error

        # Optional: You could use the base class methods here if needed
        # if all_frame_scores:
        #   stats = self._get_stats_summary(all_frame_scores)
        #   logging.info("Blurriness Stats (%s): %s", label, stats)
        #   self._save_histogram(
        #       all_frame_scores, num_bins=20, label=f"{label}_blurriness"
        #   )

        return video_average_scores


class LoopDetection(Metrics):
    """Derived class for detecting loops/repeated segments in a video."""

    def __init__(
        self,
        hash_size: int = 8,
        sample_rate: int = 1,  # Processes every Nth frame
        min_loop_duration_sec: float = 2.0,
        max_hash_diff_per_frame: int = 5,
        max_avg_hash_diff_for_sequence: float = 2.5,
    ):
        """Initializes the LoopDetection metric.

        Args:
            hash_size: The size of the perceptual hash.
            sample_rate: Process every Nth frame.
            min_loop_duration_sec: Min duration for a sequence to be a loop.
            max_hash_diff_per_frame: Max allowed Hamming distance between
                individual corresponding frames in a loop sequence.
            max_avg_hash_diff_for_sequence: Max allowed average Hamming
                distance over an entire loop sequence.
        """

        self._hash_size = hash_size
        self._sample_rate = sample_rate
        self._min_loop_duration_sec = min_loop_duration_sec
        self._max_hash_diff_per_frame = max_hash_diff_per_frame
        self._max_avg_hash_diff_for_sequence = max_avg_hash_diff_for_sequence

    def _compare_sequences_fuzzy(
        self,
        seq1_hashes: List[imagehash.ImageHash],
        seq2_hashes: List[imagehash.ImageHash],
    ) -> bool:
        """Compares two sequences of hashes fuzzily.

        Args:
            seq1_hashes: The first sequence of image hashes.
            seq2_hashes: The second sequence of image hashes.

        Returns:
            True if they are considered a match based on thresholds.
        """
        if len(seq1_hashes) != len(seq2_hashes):
            return False  # Should be same length
        if not seq1_hashes:  # Empty sequences
            # Or False, depending on definition, let's say True for empty
            return True

        total_hamming_distance = 0
        for h1, h2 in zip(seq1_hashes, seq2_hashes):
            diff = h1 - h2  # Hamming distance
            if diff > self._max_hash_diff_per_frame:
                return False
            total_hamming_distance += diff

        average_hamming_distance = total_hamming_distance / len(seq1_hashes)

        return average_hamming_distance <= self._max_avg_hash_diff_for_sequence

    def _calculate_frame_hash(self, frame: np.ndarray) -> imagehash.ImageHash:
        """Calculates the perceptual hash for a single frame."""
        # Convert frame from BGR (OpenCV) to RGB (PIL)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        # Using pHash, other options: imagehash.dhash,
        # imagehash.average_hash etc.
        return imagehash.phash(pil_image, hash_size=self._hash_size)

    def _find_loops(
        self,
        hashes: List[Tuple[float, imagehash.ImageHash]],
        min_loop_len_sampled: int,  # Renamed for clarity from min_loop_len
    ) -> List[Dict[str, float]]:
        """Finds repeating sequences using fuzzy matching and extends them.

        Args:
            hashes: A list of (timestamp, hash) tuples for sampled frames.
            min_loop_len_sampled: Minimum number of *sampled* frames for a
                loop.

        Returns:
            A list of dictionaries, each describing a detected loop. Each dict
            contains the start/end timestamps of the loop segments, duration,
            length in sampled frames, and average hash difference.
        """
        detected_loops = []
        n = len(hashes)
        if n < 2 * min_loop_len_sampled:
            return []

        # Build a map from hash to list of indices where it appears
        # (for quick lookup)
        hash_to_indices = {}
        for i, (_, h) in enumerate(hashes):
            if h not in hash_to_indices:
                hash_to_indices[h] = []
            hash_to_indices[h].append(i)

        processed_up_to_idx = -1  # To skip over already detected loop segments

        for i in range(n - min_loop_len_sampled):
            if (
                i <= processed_up_to_idx
            ):  # Skip if this 'i' is part of a loop already found
                continue

            # Sequence 1 (hashes only)
            seq1_hashes_only = [
                h for _, h in hashes[i : i + min_loop_len_sampled]
            ]

            # Find potential starting points for Sequence 2
            # The first hash of Sequence 1
            first_hash_of_seq1 = seq1_hashes_only[0]

            # Iterate through all occurrences of this first hash
            # Only consider occurrences that start *after* the current
            # Sequence 1 could end to ensure distinct loops.
            potential_j_starts = []
            for similar_hash_candidate, indices_list in hash_to_indices.items():
                # Check hashes that are "close enough" to
                # first_hash_of_seq1
                hash_diff = first_hash_of_seq1 - similar_hash_candidate
                if hash_diff <= self._max_hash_diff_per_frame:
                    for idx in indices_list:
                        # Ensure Sequence 2 starts after Sequence 1 ends
                        # and there's enough room for Sequence 2 of
                        # min_loop_len_sampled
                        if (
                            idx >= (i + min_loop_len_sampled)
                            and (idx + min_loop_len_sampled) <= n
                        ):
                            potential_j_starts.append(idx)
            potential_j_starts.sort()  # Process in order

            for j in potential_j_starts:
                # If j is part of an already processed segment
                # (from a previous longer i loop)
                if j <= processed_up_to_idx:
                    continue

                # Sequence 2 (hashes only)
                seq2_hashes_only = [
                    h for _, h in hashes[j : j + min_loop_len_sampled]
                ]

                if self._compare_sequences_fuzzy(
                    seq1_hashes_only, seq2_hashes_only
                ):
                    # Initial minimal loop found, now try to extend it
                    current_loop_len = min_loop_len_sampled
                    total_diff_accumulator = sum(
                        h1 - h2
                        for h1, h2 in zip(seq1_hashes_only, seq2_hashes_only)
                    )

                    while True:
                        idx1_next = i + current_loop_len
                        idx2_next = j + current_loop_len

                        if idx1_next < n and idx2_next < n:
                            h1_next = hashes[idx1_next][1]
                            h2_next = hashes[idx2_next][1]
                            diff_next = h1_next - h2_next

                            if diff_next <= self._max_hash_diff_per_frame:
                                new_total_diff = (
                                    total_diff_accumulator + diff_next
                                )
                                new_avg_diff = new_total_diff / (
                                    current_loop_len + 1
                                )
                                if (
                                    new_avg_diff
                                    <= self._max_avg_hash_diff_for_sequence
                                ):
                                    total_diff_accumulator = new_total_diff
                                    current_loop_len += 1
                                else:
                                    # Extending violates average diff
                                    break
                            else:
                                # Next frame pair too different for
                                # individual threshold
                                break
                        else:
                            # Reached end of video for one of the sequences
                            break

                    # Found a loop of length 'current_loop_len' (sampled frames)
                    loop_info = {
                        "start1_ts": hashes[i][0],
                        "end1_ts": hashes[i + current_loop_len - 1][0],
                        "start2_ts": hashes[j][0],
                        "end2_ts": hashes[j + current_loop_len - 1][0],
                        "duration_ts": hashes[i + current_loop_len - 1][0]
                        - hashes[i][0],
                        "loop_len_sampled_frames": current_loop_len,
                        "avg_hash_diff": (
                            total_diff_accumulator / current_loop_len
                            if current_loop_len > 0
                            else 0
                        ),
                    }
                    detected_loops.append(loop_info)
                    logging.info("Detected loop: %s", loop_info)

                    # Mark the first segment of this loop as processed so we
                    # don't re-detect sub-loops starting within it.
                    processed_up_to_idx = i + current_loop_len - 1
                    # Break from 'j' loop, move to next 'i' after the
                    # current loop
                    break
            # End of j loop
        # End of i loop
        return detected_loops

    def process(
        self,
        series: List[Tuple[str, str]],
        label: str = "label",
        text_prompt: str = "",
    ) -> List[Tuple[str, Any]]:
        """Processes videos to detect loops.

        Args:
            series: A list of tuples where each tuple contains text and video
                filepath.
            label: Eval label assigned to the series.
            text_prompt: The text prompt to use for text adherence testing
                (not used in this metric).

        Returns:
            A list of tuples, each containing the video path and information
            about detected loops (e.g., a list of loop details or count).
        """
        results = []
        for _, video_path in series:
            if not os.path.exists(video_path):
                logging.warning("Video not found; skipping: %s", video_path)
                continue

            frame_hashes = []
            # frame_count = 0
            # fps = 0
            try:
                with utils.LocalCopy(video_path) as local_vid:
                    cap = cv2.VideoCapture(local_vid)
                    if not cap.isOpened():
                        logging.error(
                            "Error: Could not open video: %s", video_path
                        )
                        results.append(
                            (video_path, {"error": "Could not open video"})
                        )
                        continue

                    fps = cap.get(cv2.CAP_PROP_FPS)
                    if fps <= 0:
                        fps = 24  # Assume default if FPS not available
                        logging.warning(
                            "Could not get FPS for %s, assuming %d",
                            video_path,
                            fps,
                        )

                    # Adjust sample rate if needed (e.g., to sample once per
                    # second)
                    # sample_every_n_frames = max(1,
                    #   int(fps / self._target_sample_rate_hz)
                    #   ) if self._target_sample_rate_hz else
                    #   self._sample_rate
                    # Using the direct frame skip rate for now
                    sample_every_n_frames = self._sample_rate

                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            break

                        current_frame_index = (
                            int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                        )
                        if current_frame_index % sample_every_n_frames == 0:
                            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                            frame_hash = self._calculate_frame_hash(frame)
                            frame_hashes.append((timestamp, frame_hash))

                    cap.release()

            except (cv2.error, FileNotFoundError, RuntimeError) as e:
                logging.exception(
                    "Error processing video %s: %s", video_path, e
                )
                results.append((video_path, {"error": str(e)}))
                continue

            # --- Loop Detection Logic ---
            min_loop_len_frames = int(
                self._min_loop_duration_sec * fps / sample_every_n_frames
            )
            if min_loop_len_frames < 2:
                min_loop_len_frames = (
                    2  # Need at least 2 frames to form a sequence
                )

            detected_loops = []
            if len(frame_hashes) > min_loop_len_frames:
                detected_loops = self._find_loops(
                    frame_hashes, min_loop_len_frames
                )

            # --- Format Result ---
            # Option 1: Just a boolean
            # result_data = bool(detected_loops)
            # Option 2: Count of loops
            result_data = len(detected_loops)
            # Option 3: Details of the first loop found
            # result_data = detected_loops[0] if detected_loops else None
            # Option 4: List of all loops found
            # result_data = detected_loops

            results.append((video_path, result_data))  # Using Option 2 for now

        return results
