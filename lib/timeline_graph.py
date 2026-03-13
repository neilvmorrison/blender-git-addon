from __future__ import annotations


def is_primary_branch(branch_name: str | None) -> bool:
    return branch_name in {"main", "master"}


def get_primary_branch_name(branch_lineages: dict[str, list[str]]) -> str | None:
    for name in ("main", "master"):
        if name in branch_lineages:
            return name
    return next(iter(branch_lineages), None)


def find_branch_meta(
    branch_name: str,
    branch_lineages: dict[str, list[str]],
    entry_index_by_hash: dict[str, int],
    primary_branch: str | None,
) -> dict:
    chain = branch_lineages.get(branch_name, [])
    other_sets = {
        name: set(hashes)
        for name, hashes in branch_lineages.items()
        if name != branch_name
    }
    anchor_hash = chain[-1] if chain else None
    base_branch = primary_branch
    unique_hashes = list(chain)

    for depth, commit_hash in enumerate(chain):
        shared_with = [n for n, hashes in other_sets.items() if commit_hash in hashes]
        if not shared_with:
            continue
        base_branch = primary_branch if primary_branch in shared_with else shared_with[0]
        anchor_hash = commit_hash
        unique_hashes = chain[:depth]
        break

    anchor_index = entry_index_by_hash.get(anchor_hash, len(entry_index_by_hash))
    return {
        "branch_name": branch_name,
        "base_branch": base_branch,
        "anchor_hash": anchor_hash,
        "anchor_index": anchor_index,
        "unique_hashes": unique_hashes,
        "dangling": bool(anchor_hash and not unique_hashes),
    }


def build_timeline_layout(
    entries: list[dict],
    branch_lineages: dict[str, list[str]],
) -> dict:
    entry_index_by_hash = {e["hash"]: i for i, e in enumerate(entries)}
    primary_branch = get_primary_branch_name(branch_lineages)

    branch_metas = {
        name: find_branch_meta(name, branch_lineages, entry_index_by_hash, primary_branch)
        for name in branch_lineages
    }

    ordered_branches = sorted(
        branch_lineages,
        key=lambda n: (
            0 if n == primary_branch else 1,
            branch_metas[n]["anchor_index"],
            n,
        ),
    )

    lane_by_branch: dict[str, int] = {n: i for i, n in enumerate(ordered_branches)}
    next_lane = len(lane_by_branch)

    owner_by_hash: dict[str, str] = {}
    if primary_branch:
        for h in branch_lineages.get(primary_branch, []):
            owner_by_hash[h] = primary_branch

    for name in ordered_branches:
        if name == primary_branch:
            continue
        for h in branch_metas[name]["unique_hashes"]:
            owner_by_hash[h] = name

    commits: list[dict] = []
    for entry in entries:
        branch_name = owner_by_hash.get(entry["hash"])
        if not branch_name and entry.get("branch_refs"):
            refs = entry["branch_refs"]
            branch_name = next((r for r in refs if r in lane_by_branch), None) or refs[0]
        if not branch_name:
            branch_name = primary_branch or f"lane-{next_lane}"
        if branch_name not in lane_by_branch:
            lane_by_branch[branch_name] = next_lane
            next_lane += 1

        commit = dict(entry)
        commit["branch_name"] = branch_name
        commit["lane"] = lane_by_branch[branch_name]
        commits.append(commit)

    index_by_hash = {c["hash"]: i for i, c in enumerate(commits)}
    max_lane = max((c["lane"] for c in commits), default=0)

    for commit in commits:
        commit["parent_links"] = []
        for parent_hash in commit.get("parents", []):
            pi = index_by_hash.get(parent_hash)
            if pi is None:
                continue
            pc = commits[pi]
            commit["parent_links"].append({
                "hash": parent_hash,
                "index": pi,
                "lane": pc["lane"],
            })
            max_lane = max(max_lane, pc["lane"])

    dangling_branches = []
    for name, meta in branch_metas.items():
        if name == primary_branch or not meta["dangling"]:
            continue
        ah = meta["anchor_hash"]
        if ah not in index_by_hash:
            continue
        dangling_branches.append({
            "branch_name": name,
            "anchor_hash": ah,
            "lane": lane_by_branch[name],
            "anchor_lane": commits[index_by_hash[ah]]["lane"],
        })
        max_lane = max(max_lane, lane_by_branch[name])

    return {
        "commits": commits,
        "max_lane": max_lane,
        "dangling_branches": dangling_branches,
    }
