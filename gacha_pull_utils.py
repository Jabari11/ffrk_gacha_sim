import random
from collections import Counter


def validate_rates(rates):
    """Raise an error if the bit odds do not sum to 1.0."""
    total = sum(rates.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Rates must sum to 1.0, got {total}")


def simulate_one_pull_multi_guarantee(rates, guarantee_rank, guarantees_per_pull=1, bits_per_pull=11):
    """
    Simulate one pull with support for multiple guarantees.

    Terms:
    - bit: one item/result inside the pull
    - qualified bit: a bit with rank >= guarantee_rank

    Example:
    - 11 1G6 means 11 bits total, and at least 1 bit of rank 6+
    - 10 2G6 means 10 bits total, and at least 2 bits of rank 6+

    The guarantees trigger as late as possible.
    Example for 10 2G6:
    - after 8 bits, if you still have 0 qualified bits, the 9th bit is forced to 6+
    - on the last bit, if you still have fewer than 2 qualified bits, the 10th bit is forced to 6+
    """
    if bits_per_pull <= 0:
        raise ValueError("bits_per_pull must be positive")
    if guarantees_per_pull < 0:
        raise ValueError("guarantees_per_pull cannot be negative")
    if guarantees_per_pull > bits_per_pull:
        raise ValueError("guarantees_per_pull cannot exceed bits_per_pull")

    ranks = list(rates.keys())
    probabilities = list(rates.values())

    guarantee_space = {k: v for k, v in rates.items() if k >= guarantee_rank}
    if guarantees_per_pull > 0 and not guarantee_space:
        raise ValueError("No ranks satisfy guarantee_rank, so the guarantee cannot work")

    guarantee_ranks = list(guarantee_space.keys())
    guarantee_total = sum(guarantee_space.values())
    guarantee_probs = [guarantee_space[k] / guarantee_total for k in guarantee_ranks] if guarantee_ranks else []

    results = []
    qualified_count = 0

    for bit_index in range(bits_per_pull):
        slots_left_including_this_one = bits_per_pull - bit_index
        minimum_qualified_needed_now = guarantees_per_pull - (slots_left_including_this_one - 1)
        must_guarantee_now = qualified_count < minimum_qualified_needed_now

        if must_guarantee_now:
            pulled = random.choices(guarantee_ranks, guarantee_probs)[0]
        else:
            pulled = random.choices(ranks, probabilities)[0]

        results.append(pulled)
        if pulled >= guarantee_rank:
            qualified_count += 1

    return results


def simulate_one_run_counts(rates, guarantee_rank, guarantees_per_pull, bits_per_pull, pulls_per_run):
    """Simulate one full run and return a Counter of all ranks seen in that run."""
    run_counts = Counter()
    for _ in range(pulls_per_run):
        pull_results = simulate_one_pull_multi_guarantee(
            rates=rates,
            guarantee_rank=guarantee_rank,
            guarantees_per_pull=guarantees_per_pull,
            bits_per_pull=bits_per_pull,
        )
        run_counts.update(pull_results)
    return run_counts
