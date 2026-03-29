from collections import Counter

from gacha_pull_utils import validate_rates, simulate_one_pull_multi_guarantee


def pity_tokens_earned(pity_rules, start_pull_count, total_pull_count):
    """
    Return pity tokens earned by crossing thresholds in (start_pull_count, total_pull_count].
    pity_rules example:
      [
        {"after_pulls": 5, "allow": {17, 18}},
        {"after_pulls": 10, "allow": {17, 18, 19, 20}},
      ]
    """
    tokens = []
    for rule in pity_rules:
        threshold = rule["after_pulls"]
        if start_pull_count < threshold <= total_pull_count:
            tokens.append(set(rule["allow"]))
    return tokens


def can_cover_with_pity(missing_targets, pity_tokens):
    """
    Can pity tokens be assigned to distinct missing targets?
    """
    missing = list(missing_targets)
    if not missing:
        return True
    if len(pity_tokens) < len(missing):
        return False

    adj = []
    for token in pity_tokens:
        adj.append([t for t in missing if t in token])

    match_target_to_token = {}

    def dfs(token_idx, visited):
        for target in adj[token_idx]:
            if target in visited:
                continue
            visited.add(target)
            if target not in match_target_to_token or dfs(match_target_to_token[target], visited):
                match_target_to_token[target] = token_idx
                return True
        return False

    matched = 0
    for token_idx in range(len(pity_tokens)):
        if dfs(token_idx, set()):
            matched += 1

    return matched >= len(missing)


def evaluate_run_success(target_ranks, seen_targets, pity_tokens):
    missing = set(target_ranks) - set(seen_targets)
    return can_cover_with_pity(missing, pity_tokens)


def simulate_one_run(
    pulls_to_simulate,
    rates,
    guarantee_rank,
    target_ranks,
    pity_rules,
    start_pull_count=0,
    seed_seen_targets=None,
    bits_per_pull=11,
    guarantees_per_pull=1,
):
    """
    Simulate the remaining pulls of a single in-progress run.

    start_pull_count:
      how many pulls have already happened in this run before resuming

    pulls_to_simulate:
      how many additional pulls to simulate from this point
    """
    seed_seen_targets = set(seed_seen_targets or [])
    target_ranks = set(target_ranks)

    run_bit_results = Counter()
    newly_seen_targets = set()

    for _ in range(pulls_to_simulate):
        pull_results = simulate_one_pull_multi_guarantee(
            rates=rates,
            guarantee_rank=guarantee_rank,
            guarantees_per_pull=guarantees_per_pull,
            bits_per_pull=bits_per_pull,
        )
        run_bit_results.update(pull_results)

        for rank in pull_results:
            if rank in target_ranks:
                newly_seen_targets.add(rank)

    total_pull_count = start_pull_count + pulls_to_simulate
    pity_tokens = pity_tokens_earned(
        pity_rules=pity_rules,
        start_pull_count=start_pull_count,
        total_pull_count=total_pull_count
    )

    seen_targets = seed_seen_targets | newly_seen_targets
    success = evaluate_run_success(
        target_ranks=target_ranks,
        seen_targets=seen_targets,
        pity_tokens=pity_tokens
    )

    return {
        "success": success,
        "seen_targets": seen_targets,
        "newly_seen_targets": newly_seen_targets,
        "pity_tokens": pity_tokens,
        "bit_results": run_bit_results,
    }


def simulate_many_runs(
    total_run_pulls,
    iterations,
    rates,
    guarantee_rank,
    target_ranks,
    pity_rules,
    start_pull_count=0,
    seed_seen_targets=None,
    bits_per_pull=11,
    guarantees_per_pull=1,
):
    """
    Estimate success probability for a run with prior progress.

    total_run_pulls:
      total pull budget for the run
    start_pull_count:
      pulls already spent in the current real run
    """
    validate_rates(rates)

    if total_run_pulls < start_pull_count:
        raise ValueError("total_run_pulls must be >= start_pull_count")

    print(f"Validity checks passed, running {iterations} iterations...")
    pulls_to_simulate = total_run_pulls - start_pull_count
    overall_bit_results = Counter()
    successes = 0

    target_bits_total = 0
    non_trash_bits_total = 0

    for _ in range(iterations):
        result = simulate_one_run(
            pulls_to_simulate=pulls_to_simulate,
            rates=rates,
            guarantee_rank=guarantee_rank,
            target_ranks=target_ranks,
            pity_rules=pity_rules,
            start_pull_count=start_pull_count,
            seed_seen_targets=seed_seen_targets,
            bits_per_pull=bits_per_pull,
            guarantees_per_pull=guarantees_per_pull,
        )

        overall_bit_results.update(result["bit_results"])

        run_bit_results = result["bit_results"]
        target_bits_total += sum(run_bit_results[r] for r in target_ranks)
        non_trash_bits_total += sum(count for rank, count in run_bit_results.items() if rank >= guarantee_rank)

        if result["success"]:
            successes += 1

    total_bits = iterations * pulls_to_simulate * bits_per_pull
    total_simulated_pulls = iterations * pulls_to_simulate

    average_results = {
        rank: (overall_bit_results[rank] / total_bits if total_bits > 0 else 0.0)
        for rank in rates
    }
    success_rate = (successes / iterations) * 100 if iterations > 0 else 0.0

    avg_target_bits_per_pull = (
        target_bits_total / total_simulated_pulls if total_simulated_pulls > 0 else 0.0
    )
    avg_non_trash_bits_per_pull = (
        non_trash_bits_total / total_simulated_pulls if total_simulated_pulls > 0 else 0.0
    )

    print(
        f"Simulation: {iterations} runs, "
        f"total_run_pulls={total_run_pulls}, "
        f"start_pull_count={start_pull_count}, "
        f"remaining_pulls={pulls_to_simulate}, "
        f"guarantees_per_pull={guarantees_per_pull}, "
        f"guarantee_rank={guarantee_rank}"
    )
    print("Average probability per bit (empirical):")
    for rank, avg in sorted(average_results.items(), reverse=True):
        print(f"  Rank {rank}: {avg:.4f}")

    print(f"Average target bits per pull: {avg_target_bits_per_pull:.4f}")
    print(f"Average non-trash bits per pull: {avg_non_trash_bits_per_pull:.4f}")
    print(f"Run success rate: {success_rate:.2f}%")

    return {
        "average_results": average_results,
        "avg_target_bits_per_pull": avg_target_bits_per_pull,
        "avg_non_trash_bits_per_pull": avg_non_trash_bits_per_pull,
        "success_rate": success_rate,
    }


# ============================================================
# USER-EDITABLE SECTION
# ============================================================
# Change the values below to match the banner you want to test.
#
# IMPORTANT TERMS:
# - "bit"  = one item/result inside a pull
# - "pull" = one full currency spend (usually 11 bits)
# - "run"  = your full attempt on the banner (example: up to 10 pulls total)
#
# This simulator answers:
# "Given this banner, this pity system, and my current progress so far,
# what are my odds of finishing successfully by the end of the run?"
# ============================================================


# ------------------------------------------------------------
# BANNER ODDS
# ------------------------------------------------------------
# Put the chance for EACH possible bit result here.
#
# Format:
#   result_id: chance_per_bit
#
# Notes:
# - These chances must add up to exactly 1.0
# - The simulator will stop with an error if they do not
# - Usually "0" is trash / unwanted junk
# - Higher numbers here are just IDs / tiers used by the sim
rates = {
    20: 0.01,
    19: 0.01,
    18: 0.01,
    17: 0.01,
    16: 0.1004,
    0: 1 - 0.1404,
}


# ------------------------------------------------------------
# PITY RULES
# ------------------------------------------------------------
# List any pity selections you earn during the run.
#
# Format:
#   {"after_pulls": X, "allow": {IDs you may choose from}}
#
# Meaning:
# - after_pulls = when that pity reward is earned
# - allow = which target IDs that pity can select
#
# IMPORTANT:
# - Pity is checked at the END of the run
# - Pity does NOT affect the pulls during the run
# - If you can choose only one relic from a pity reward, list one rule
# - If there are multiple pity rewards, list multiple rules
pity_rules = [
    {"after_pulls": 5, "allow": {17, 18}},
    {"after_pulls": 10, "allow": {17, 18, 19, 20}},
]


# ------------------------------------------------------------
# RUN SETTINGS
# ------------------------------------------------------------
# total_run_pulls
#   Total pull budget for the full run.
#
# iterations
#   Number of simulated runs to test.
#   More iterations = more accurate, but slower.
#
# guarantee_rank
#   Minimum rank/tier that counts as guaranteed non-trash.
#
# guarantees_per_pull
#   Number of guaranteed rank-or-better bits per pull.
#   For the classic old sim behavior, leave this as 1.
#
# target_ranks
#   The specific IDs you are trying to collect for success.
#
# bits_per_pull
#   Number of bits/items in each pull.
#
# start_pull_count
#   How many pulls you have ALREADY spent on this same run before resuming.
#
# seed_seen_targets
#   Which target IDs you have ALREADY hit earlier in this same run.
total_run_pulls = 5
iterations = 100000
guarantee_rank = 1
guarantees_per_pull = 1
target_ranks = {20, 19, 18, 17}
bits_per_pull = 11
start_pull_count = 0
seed_seen_targets = set()


simulate_many_runs(
    total_run_pulls=total_run_pulls,
    iterations=iterations,
    rates=rates,
    guarantee_rank=guarantee_rank,
    target_ranks=target_ranks,
    pity_rules=pity_rules,
    start_pull_count=start_pull_count,
    seed_seen_targets=seed_seen_targets,
    bits_per_pull=bits_per_pull,
    guarantees_per_pull=guarantees_per_pull,
)
