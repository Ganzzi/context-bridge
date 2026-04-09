# Smart Chunk Markdown Algorithm

This document describes the `smart_chunk_markdown` algorithm found in the `chunking_service.py` file.

## Overview

The `smart_chunk_markdown` function is designed to break down a large Markdown document into smaller, manageable chunks. The primary goal is to maintain the structural integrity of the Markdown content by attempting to split the text at logical boundaries such as code blocks, paragraphs, or sentences, rather than at arbitrary points.

## Algorithm Steps

The algorithm processes the Markdown string iteratively. Here's a step-by-step breakdown of its logic:

1.  **Initialization**:
    *   It initializes an empty list called `chunks` to store the text of each chunk.
    *   A `start` pointer is set to `0`, representing the beginning of the current chunk.
    *   The total length of the markdown content is calculated.

2.  **Iteration**: The algorithm iterates through the markdown content as long as the `start` pointer is less than the total length.

3.  **Chunk Boundary Calculation**:
    *   For each iteration, it calculates a potential `end` position for the chunk by adding the `chunk_size` to the `start` position.
    *   If the calculated `end` is beyond the end of the document, the remaining part of the document is taken as the last chunk, and the loop terminates.

4.  **Boundary Prioritization**: The algorithm then tries to find a better `end` position by looking for structural boundaries within the current `start` to `end` slice. It prioritizes boundaries in the following order:
    *   **Code Blocks**: It first searches for the last occurrence of a code block delimiter ("\`\`\`"). If found, and if it's reasonably far into the chunk (more than 30% of `chunk_size`), it sets the `end` of the chunk to the beginning of the code block delimiter. This prevents splitting code blocks.
    *   **Paragraphs**: If no suitable code block boundary is found, it looks for the last paragraph break (`\n\n`). If a paragraph break is found more than 30% into the chunk, the `end` is set at that break.
    *   **Sentences**: If neither a code block nor a paragraph break is found, it searches for the last sentence-ending period followed by a space (`. `). If found more than 30% into the chunk, the `end` is set right after the period and space.
    *   **Default**: If none of the above structural boundaries are found, the `end` remains at the originally calculated `start + chunk_size`.

5.  **Chunk Extraction**:
    *   The text between the `start` and the determined `end` position is extracted.
    *   Any leading or trailing whitespace is removed.
    *   If the resulting chunk is not empty, it's added to the `chunks` list.

6.  **Advancing the Pointer**: The `start` pointer is moved to the `end` position for the next iteration.

7.  **Final Output**: The function returns a list of strings, where each string is a chunk of the original Markdown content.

## Key Parameters

*   `markdown` (str): The input Markdown content.
*   `chunk_size` (int): The desired maximum size of each chunk in characters. Defaults to `DEFAULT_MAX_CHUNK_SIZE`.