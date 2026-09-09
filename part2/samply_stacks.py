"""Export native stacks from samply 0.13's profile and symbol sidecar to Perfetto."""

from collections import Counter
import json

from export_stacks import validate_stacks


def export_samply(profile_path, output_path):
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    symbols = json.loads(profile_path.with_suffix(".syms.json").read_text(encoding="utf-8"))
    names = symbols["string_table"]
    libraries = {}
    for library in symbols["data"]:
        libraries[(library["debug_name"], library["code_id"])] = {
            address: names[library["symbol_table"][index]["symbol"]]
            for address, index in library["known_addresses"] if index is not None
        }
    counts = Counter()
    for thread in profile["threads"]:
        frames = []
        for frame, function in enumerate(thread["frameTable"]["func"]):
            name = thread["stringArray"][thread["funcTable"]["name"][function]]
            resource = thread["funcTable"]["resource"][function]
            if resource is not None and resource >= 0:
                lib_index = thread["resourceTable"]["lib"][resource]
                if lib_index is not None and lib_index >= 0:
                    library = profile["libs"][lib_index]
                    address = thread["frameTable"]["address"][frame]
                    lookup = libraries.get((library["debugName"], library["codeId"]), {})
                    name = lookup.get(address, f'{library["name"]}!{name}')
            # Semicolons delimit frames in the collapsed format.
            frames.append(name.replace(";", ":").replace("\n", " ").replace("\r", " "))
        stacks = []
        for index, frame in enumerate(thread["stackTable"]["frame"]):
            prefix = thread["stackTable"]["prefix"][index]
            stacks.append((stacks[prefix] + ";" if prefix is not None else "") + frames[frame])
        samples = thread["samples"]
        if samples["weightType"] != "samples":
            raise ValueError("Expected sample-count weights from samply")
        weights = samples.get("weight") or [1] * samples["length"]
        for stack, weight in zip(samples["stack"], weights):
            if stack is not None and weight > 0:
                counts[stacks[stack]] += weight
    data = "".join(f"{stack} {count}\n" for stack, count in sorted(counts.items())).encode("utf-8")
    total = validate_stacks(data)
    with output_path.open("xb") as output:
        output.write(data)
    return total
