#!/usr/bin/env python3
"""
Word Search Puzzle Generator (Fixed Verification)
- Proper solution verification
- Reliable puzzle generation
"""

import requests
import random
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
THEMES_FILE = Path("themes.json")
THEME_WORDS_CACHE = Path("theme_words.json")
GRID_SIZES = [8, 10, 12, 15]
DIFFICULTIES = ["easy", "medium", "hard"]
PUZZLES_PER_COMBO = 3500
OUTPUT_DIR = Path("data")

ALL_DIRECTIONS = [
    (0, 1),  # Right
    (1, 0),  # Down
    (1, 1),  # Down-Right
    (-1, 1),  # Up-Right
    (0, -1),  # Left
    (-1, 0),  # Up
    (-1, -1),  # Up-Left
    (1, -1)  # Down-Left
]

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


# ------------------------------------------------------------
# Load themes
# ------------------------------------------------------------
def load_themes() -> List[str]:
    """Load themes from JSON file."""
    try:
        with open(THEMES_FILE, 'r') as f:
            themes = json.load(f)
        logging.info(f"Loaded {len(themes)} themes from {THEMES_FILE}")
        return themes
    except FileNotFoundError:
        logging.error(f"Themes file not found: {THEMES_FILE}")
        raise
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in {THEMES_FILE}")
        raise


# ------------------------------------------------------------
# Theme words cache management
# ------------------------------------------------------------
def load_theme_cache() -> Dict[str, List[str]]:
    """Load cached theme words from file."""
    if THEME_WORDS_CACHE.exists():
        try:
            with open(THEME_WORDS_CACHE, 'r') as f:
                cache = json.load(f)
            logging.info(f"Loaded theme cache with {len(cache)} themes")
            return cache
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not load theme cache: {e}")
            return {}
    return {}


def save_theme_cache(cache: Dict[str, List[str]]) -> None:
    """Save theme words cache to file."""
    try:
        with open(THEME_WORDS_CACHE, 'w') as f:
            json.dump(cache, f, indent=2)
        logging.info(f"Saved theme cache with {len(cache)} themes")
    except IOError as e:
        logging.error(f"Could not save theme cache: {e}")


def fetch_theme_words(theme: str) -> List[str]:
    """Fetch words related to a theme from Datamuse API."""
    try:
        url = f"https://api.datamuse.com/words?rel_trg={theme}&max=100"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        words = [item['word'].upper() for item in response.json()
                 if 'word' in item and item['word'].isalpha()]
        logging.debug(f"Fetched {len(words)} words for theme: {theme}")
        return words
    except requests.RequestException as e:
        logging.warning(f"Failed to fetch words for {theme}: {e}")
        return []
    except (KeyError, ValueError) as e:
        logging.warning(f"Invalid response for {theme}: {e}")
        return []


def update_theme_cache(themes: List[str]) -> Dict[str, List[str]]:
    """
    Update the theme cache by fetching missing themes.
    Returns the complete cache.
    """
    cache = load_theme_cache()
    return cache
    # If cache exists and has most themes, use it
    if cache and len(cache) >= len(themes) * 0.5:
        logging.info(f"Using existing cache with {len(cache)} themes")
        return cache

    # Otherwise fetch missing themes
    logging.info(f"Fetching words for {len(themes)} themes")

    for theme in themes:
        if theme not in cache or len(cache.get(theme, [])) < 20:
            words = fetch_theme_words(theme)
            if words:
                cache[theme] = words
                logging.debug(f"Cached {len(words)} words for '{theme}'")

            # Respect API rate limits
            time.sleep(0.3)

    save_theme_cache(cache)
    return cache


# ------------------------------------------------------------
# SIMPLE Duplicate Prevention
# ------------------------------------------------------------
def has_similar_words(words: List[str]) -> bool:
    """Check if list contains obvious duplicates like wetland/wetlands."""
    word_set = set(words)

    # Check for exact matches with 's' suffix
    for word in words:
        # Check word + 'S'
        if word + 'S' in word_set:
            return True
        # Check word without trailing 'S'
        if word.endswith('S') and word[:-1] in word_set:
            return True
        # Check word + 'ES'
        if word + 'ES' in word_set:
            return True
        if word.endswith('ES') and word[:-2] in word_set:
            return True

    return False


# ------------------------------------------------------------
# Simple Difficulty Profiles
# ------------------------------------------------------------
def get_difficulty_params(difficulty: str, grid_size: int) -> Dict:
    """Get parameters for a specific difficulty level."""

    if difficulty == "easy":
        return {
            'difficulty_label': 'easy',
            'directions': [(0, 1), (1, 0)],  # Only Right and Down
            'backwards_ratio': 0.00,
            'word_count': max(4, min(6, grid_size // 2)),
            'min_len': 4,
            'max_len': min(6, grid_size - 2),
            'placement_attempts': 200,
            'min_words_required': 3
        }

    elif difficulty == "medium":
        return {
            'difficulty_label': 'medium',
            'directions': [(0, 1), (1, 0), (1, 1), (-1, 1)],  # 4 directions
            'backwards_ratio': 0.15,
            'word_count': max(5, min(8, grid_size // 2 + 1)),
            'min_len': 4,
            'max_len': min(8, grid_size - 2),
            'placement_attempts': 200,
            'min_words_required': 4
        }

    else:  # hard
        return {
            'difficulty_label': 'hard',
            'directions': ALL_DIRECTIONS,  # All 8 directions
            'backwards_ratio': 0.25,
            'word_count': max(6, min(10, grid_size // 2 + 2)),
            'min_len': 4,
            'max_len': min(10, grid_size - 2),
            'placement_attempts': 300,
            'min_words_required': 4
        }


# ------------------------------------------------------------
# Word Filtering
# ------------------------------------------------------------
def filter_words(words: List[str], min_len: int, max_len: int) -> List[str]:
    """Filter words by length."""
    filtered = []
    seen = set()

    for w in words:
        w_upper = w.upper()
        if (min_len <= len(w_upper) <= max_len and
                w_upper.isalpha() and
                w_upper not in seen):
            seen.add(w_upper)
            filtered.append(w_upper)

    return filtered


# ------------------------------------------------------------
# Placement Helpers
# ------------------------------------------------------------
def can_place_word(grid: List[List[str]], word: str, r: int, c: int,
                   dy: int, dx: int, size: int) -> bool:
    """Check if a word can be placed at the given position."""
    # Check bounds
    end_r = r + (len(word) - 1) * dy
    end_c = c + (len(word) - 1) * dx
    if not (0 <= end_r < size and 0 <= end_c < size):
        return False

    # Check each cell
    for i, ch in enumerate(word):
        rr = r + i * dy
        cc = c + i * dx
        if grid[rr][cc] not in ('', ch):
            return False

    return True


def place_word(grid: List[List[str]], word: str, r: int, c: int, dy: int, dx: int) -> None:
    """Place a word on the grid."""
    for i, ch in enumerate(word):
        grid[r + i * dy][c + i * dx] = ch


# ------------------------------------------------------------
# FIXED Puzzle Generator
# ------------------------------------------------------------
def generate_puzzle(theme: str, size: int, params: Dict,
                    available_words: List[str], puzzle_id: str) -> Optional[Dict]:
    """Generate a single word search puzzle with fixed verification."""

    # Initialize empty grid
    grid = [['' for _ in range(size)] for _ in range(size)]
    directions = params['directions']

    # Filter words
    filtered = filter_words(available_words, params['min_len'], params['max_len'])

    if len(filtered) < params['word_count']:
        logging.debug(f"Not enough filtered words for {puzzle_id}")
        return None

    # Select words
    random.shuffle(filtered)
    selected_words = filtered[:params['word_count']]

    # Check for obvious duplicates
    if has_similar_words(selected_words):
        logging.debug(f"Similar words detected in selection for {puzzle_id}")
        return None

    placed_words = []
    solution = []

    # Sort by length (longer first for better placement)
    selected_words.sort(key=len, reverse=True)

    # Track used starting positions to avoid overlap
    used_positions = set()

    # Place words
    for word in selected_words:
        original_word = word

        # Decide if we should reverse this word
        if random.random() < params['backwards_ratio']:
            word = word[::-1]

        placed = False

        # Try to place the word
        for _ in range(params['placement_attempts']):
            # Choose random direction
            dy, dx = random.choice(directions)

            # Choose random starting position that fits
            max_r = size - len(word) if dy >= 0 else size - 1
            max_c = size - len(word) if dx >= 0 else size - 1
            min_r = 0 if dy >= 0 else len(word) - 1
            min_c = 0 if dx >= 0 else len(word) - 1

            if max_r < min_r or max_c < min_c:
                continue

            r = random.randint(min_r, max_r)
            c = random.randint(min_c, max_c)

            # Skip positions that might overlap too much
            if (r, c) in used_positions and random.random() > 0.7:
                continue

            if can_place_word(grid, word, r, c, dy, dx, size):
                place_word(grid, word, r, c, dy, dx)

                # Record solution
                pos = r * size + c
                dir_idx = ALL_DIRECTIONS.index((dy, dx))
                solution.append(f"{pos};{dir_idx};{len(original_word)};{original_word}")
                placed_words.append(original_word)

                # Mark this position as used
                used_positions.add((r, c))

                placed = True
                break

        if not placed:
            # Try brute force placement
            for r in range(size):
                for c in range(size):
                    for dy, dx in directions:
                        if can_place_word(grid, word, r, c, dy, dx, size):
                            place_word(grid, word, r, c, dy, dx)
                            pos = r * size + c
                            dir_idx = ALL_DIRECTIONS.index((dy, dx))
                            solution.append(f"{pos};{dir_idx};{len(original_word)};{original_word}")
                            placed_words.append(original_word)
                            used_positions.add((r, c))
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break

    # Check if we placed enough words
    if len(placed_words) < params['min_words_required']:
        logging.debug(f"Only placed {len(placed_words)} words for {puzzle_id}")
        return None

    # FIXED: Verify solution BEFORE filling grid
    if not verify_solution_intermediate(grid, solution, size):
        logging.debug(f"Intermediate solution verification failed for {puzzle_id}")
        return None

    # Fill empty cells with random letters
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    for r in range(size):
        for c in range(size):
            if not grid[r][c]:
                grid[r][c] = random.choice(letters)

    # FIXED: Final verification with filled grid
    if not verify_solution_final(grid, solution, size):
        logging.debug(f"Final solution verification failed for {puzzle_id}")
        return None

    # Remove duplicates from placed_words
    unique_words = []
    seen_words = set()
    for w in placed_words:
        if w not in seen_words:
            seen_words.add(w)
            unique_words.append(w)

    # Final check for similar words
    if has_similar_words(unique_words):
        logging.debug(f"Similar words in final puzzle {puzzle_id}")
        return None

    # Flatten grid to string
    flat_grid = ''.join(''.join(row) for row in grid)

    return {
        'id': puzzle_id,
        'theme': theme,
        'grid': flat_grid,
        'solution': ','.join(solution),
        'gridSize': size,
        'difficulty': params['difficulty_label'],
        'wordCount': len(unique_words),
        'wordlist': sorted(unique_words, key=lambda w: (len(w), w.lower()))
    }


def verify_solution_intermediate(grid: List[List[str]], solution: List[str], size: int) -> bool:
    """Verify solution on intermediate grid (before filling with random letters)."""
    try:
        for sol in solution:
            # Parse solution entry
            parts = sol.split(';')
            if len(parts) != 4:
                logging.debug(f"Invalid solution format: {sol}")
                return False

            pos_str, dir_idx_str, length_str, original_word = parts

            # Convert to proper types
            try:
                start_pos = int(pos_str)
                dir_idx = int(dir_idx_str)
                word_length = int(length_str)
            except ValueError:
                logging.debug(f"Invalid numeric values in solution: {sol}")
                return False

            # Validate indices
            if dir_idx < 0 or dir_idx >= len(ALL_DIRECTIONS):
                logging.debug(f"Invalid direction index: {dir_idx}")
                return False

            if word_length != len(original_word):
                logging.debug(f"Length mismatch: {word_length} vs {len(original_word)}")
                return False

            # Get direction
            dy, dx = ALL_DIRECTIONS[dir_idx]

            # Calculate start position
            start_row = start_pos // size
            start_col = start_pos % size

            # Check bounds
            end_row = start_row + (word_length - 1) * dy
            end_col = start_col + (word_length - 1) * dx
            if not (0 <= end_row < size and 0 <= end_col < size):
                logging.debug(f"Word out of bounds: {original_word}")
                return False

            # Check each letter matches
            for i in range(word_length):
                r = start_row + i * dy
                c = start_col + i * dx
                if grid[r][c] != original_word[i]:
                    # Check if it's the reversed version
                    if grid[r][c] != original_word[word_length - 1 - i]:
                        logging.debug(f"Letter mismatch at ({r},{c}): {grid[r][c]} != {original_word[i]}")
                        return False

        return True
    except Exception as e:
        logging.debug(f"Error in verify_solution_intermediate: {e}")
        return False


def verify_solution_final(grid: List[List[str]], solution: List[str], size: int) -> bool:
    """Verify solution on final grid (after filling with random letters)."""
    try:
        for sol in solution:
            # Parse solution entry
            parts = sol.split(';')
            if len(parts) != 4:
                return False

            pos_str, dir_idx_str, length_str, original_word = parts

            # Convert to proper types
            try:
                start_pos = int(pos_str)
                dir_idx = int(dir_idx_str)
                word_length = int(length_str)
            except ValueError:
                return False

            # Validate indices
            if dir_idx < 0 or dir_idx >= len(ALL_DIRECTIONS):
                return False

            # Get direction
            dy, dx = ALL_DIRECTIONS[dir_idx]

            # Calculate start position
            start_row = start_pos // size
            start_col = start_pos % size

            # Reconstruct word from grid
            reconstructed = ''
            for i in range(word_length):
                r = start_row + i * dy
                c = start_col + i * dx
                reconstructed += grid[r][c]

            # Check if it matches original word or its reverse
            if reconstructed != original_word and reconstructed != original_word[::-1]:
                logging.debug(f"Word mismatch: {reconstructed} != {original_word} or reverse")
                return False

        return True
    except Exception as e:
        logging.debug(f"Error in verify_solution_final: {e}")
        return False


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    """Main function to generate puzzles."""
    # Load themes
    themes = load_themes()

    # Update theme cache
    theme_cache = update_theme_cache(themes)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Generate puzzles for each grid size and difficulty
    for size in GRID_SIZES:
        for diff in DIFFICULTIES:
            folder = OUTPUT_DIR / str(size) / diff
            folder.mkdir(parents=True, exist_ok=True)

            params = get_difficulty_params(diff, size)
            file_counter = 1  # This tracks the NEXT file number to use
            puzzles_made = 0
            failed_attempts = 0
            max_failed_attempts = 300
            total_attempts = 0  # Track total attempts for rate calculation

            logging.info(f"Generating {PUZZLES_PER_COMBO} puzzles for size={size}, difficulty={diff}")

            # Find themes with enough words
            available_themes = []
            for theme in themes:
                words = theme_cache.get(theme, [])
                if not words:
                    continue

                filtered = filter_words(words, params['min_len'], params['max_len'])
                if len(filtered) >= params['word_count']:
                    available_themes.append((theme, filtered))

            if not available_themes:
                logging.error(f"No themes with enough words for {size}-{diff}")
                continue

            logging.info(f"Found {len(available_themes)} themes for {size}-{diff}")

            while puzzles_made < PUZZLES_PER_COMBO and failed_attempts < max_failed_attempts:
                # Randomly select a theme
                theme, usable_words = random.choice(available_themes)

                # Generate puzzle - use a temporary ID for logging
                puzzle_id = f"{size}-{diff}-attempt-{total_attempts}"

                try:
                    puzzle = generate_puzzle(theme, size, params, usable_words, puzzle_id)

                    if not puzzle:
                        failed_attempts += 1
                        total_attempts += 1

                        if failed_attempts % 50 == 0:
                            logging.warning(f"{failed_attempts} failed attempts for {size}-{diff}")
                        continue

                    # Reset failed attempts on success
                    failed_attempts = 0

                    # Quick validation
                    if len(puzzle['grid']) != size * size:
                        total_attempts += 1
                        continue

                    if has_similar_words(puzzle['wordlist']):
                        total_attempts += 1
                        continue

                    # Update puzzle ID with the actual file number
                    puzzle['id'] = f"{size}-{diff}-{file_counter}"

                    # Save puzzle
                    output_file = folder / f"{file_counter}.json"
                    with open(output_file, 'w') as f:
                        json.dump(puzzle, f, separators=(',', ':'))

                    puzzles_made += 1
                    file_counter += 1  # Only increment when we save a file
                    total_attempts += 1

                    if puzzles_made % 100 == 0:
                        success_rate = puzzles_made / total_attempts if total_attempts > 0 else 0
                        logging.info(f"  Generated {puzzles_made}/{PUZZLES_PER_COMBO} puzzles")
                        logging.info(f"  Success rate: {success_rate:.1%}")

                except Exception as e:
                    logging.error(f"Error generating puzzle {puzzle_id}: {e}")
                    failed_attempts += 1
                    total_attempts += 1
                    continue

            if failed_attempts >= max_failed_attempts:
                logging.error(f"Too many failed attempts for {size}-{diff}, generated {puzzles_made} puzzles")
            else:
                success_rate = puzzles_made / total_attempts if total_attempts > 0 else 0
                logging.info(f"Completed: size={size}, difficulty={diff} - {puzzles_made} puzzles")
                logging.info(f"  Success rate: {success_rate:.1%}")

    logging.info("Generation complete!")

if __name__ == "__main__":
    main()