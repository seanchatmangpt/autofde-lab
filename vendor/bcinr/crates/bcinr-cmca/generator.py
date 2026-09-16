#!/usr/bin/env python3
import hashlib
import os
import re
import sys

F_MAX = 32
K_MAX = 16
Q_MAX = 16
N_MAX = 256


def hash_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def strip_ttl_comment(line):
    """Strip a trailing '#'-comment from a single Turtle line, without
    corrupting '#' characters that appear inside a double-quoted string
    literal (e.g. a URL fragment or an ID embedded in a note).

    Turtle string literals in this generator's supported subset are
    double-quoted (`"..."`), with `\\"` as the escape for an embedded quote.
    We scan left to right, tracking whether we're inside such a literal, and
    only treat '#' as a comment marker when we are not.
    """
    in_string = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and in_string:
            # Skip the escaped character so a literal `\"` doesn't toggle
            # the in_string state.
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
        elif ch == "#" and not in_string:
            return line[:i].strip()
        i += 1
    return line.strip()


def parse_ttl(file_path):
    classes = {}
    properties = {}

    with open(file_path, "r") as f:
        content = f.read()

    lines = content.split("\n")
    clean_lines = []
    for line in lines:
        clean_lines.append(strip_ttl_comment(line))
    clean_content = "\n".join(clean_lines)

    # Reject unsupported constructs
    if '"""' in clean_content or "'''" in clean_content:
        raise ValueError("Unsupported Turtle construct: multiline literals")
    if "@en" in clean_content or '"@' in clean_content:
        raise ValueError("Unsupported Turtle construct: language tags")
    if "_:" in clean_content:
        raise ValueError("Unsupported Turtle construct: blank nodes")
    if "(" in clean_content or ")" in clean_content:
        raise ValueError("Unsupported Turtle construct: collections")
    if "[" in clean_content or "]" in clean_content:
        raise ValueError(
            "Unsupported Turtle construct: nested blank-node property lists"
        )
    if "{" in clean_content or "}" in clean_content:
        raise ValueError("Unsupported Turtle construct: named graphs")
    if "<" in clean_content and ">" in clean_content:
        # Assuming our format uses pure prefixed names
        if re.search(r"<[^>]+>", clean_content):
            raise ValueError("Unsupported Turtle construct: relative IRIs")

    for line in clean_lines:
        if not line:
            continue
        if line.startswith("@prefix"):
            continue

        if line.endswith("."):
            line = line[:-1].strip()

        parts = re.split(r"\s+", line, maxsplit=2)
        if len(parts) < 3:
            continue

        subj, pred, obj = parts[0], parts[1], parts[2]

        # Parse typed literal explicitly
        if "^^" in obj:
            if (
                not obj.endswith("^^xsd:decimal")
                and not obj.endswith("^^xsd:float")
                and not obj.endswith("^^xsd:integer")
            ):
                raise ValueError(f"Unsupported typed literal: {obj}")

        # Clean value
        val_match = re.match(r'^"([^"]+)"', obj)
        if val_match:
            val_str = val_match.group(1)
            try:
                if "." in val_str:
                    val = float(val_str)
                else:
                    val = int(val_str)
            except ValueError:
                val = val_str
        else:
            val = obj

        if pred == "a":
            classes[subj] = val
        else:
            if subj not in properties:
                properties[subj] = {}
            if pred == "cmca:dependsOn":
                if "cmca:dependsOn" not in properties[subj]:
                    properties[subj]["cmca:dependsOn"] = []
                if val in properties[subj]["cmca:dependsOn"]:
                    raise ValueError(
                        "Unsupported Turtle construct: repeated properties"
                    )
                properties[subj]["cmca:dependsOn"].append(val)
            else:
                if pred in properties[subj]:
                    raise ValueError(
                        "Unsupported Turtle construct: repeated properties"
                    )
                properties[subj][pred] = val

    return classes, properties


def validate_shapes(classes, properties):
    # SHACL/ShEx Equivalent Admission Check
    for subj, cls in classes.items():
        if cls == "cmca:SemanticObject":
            props = properties.get(subj, {})
            # Validate required properties for SemanticObject (units, types)
            if "cmca:businessValue" in props:
                assert isinstance(props["cmca:businessValue"], (int, float)), (
                    "businessValue must be numeric"
                )
        elif cls == "cmca:MeasureHead":
            pass
        elif cls == "cmca:Lens":
            props = properties.get(subj, {})
            assert "cmca:lensExponent" in props, "Lens must have exponent"
            assert isinstance(props["cmca:lensExponent"], (int, float)), (
                "lensExponent must be numeric"
            )


def to_q16_16(val):
    scaled = int(round(val * 65536))
    return scaled


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) >= 3:
        ttl_path = sys.argv[1]
        out_path = sys.argv[2]
    else:
        ttl_path = os.path.join(script_dir, "ontology", "cmca-rdf.ttl")
        out_path = os.path.join(
            script_dir, "src", "generated", "consequence_mass", "case_studies.rs"
        )

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(ttl_path):
        print(f"Error: TTL file not found at {ttl_path}", file=sys.stderr)
        sys.exit(1)

    classes, properties = parse_ttl(ttl_path)
    validate_shapes(classes, properties)

    # Digests
    input_digest = hash_file(ttl_path)
    generator_digest = hash_file(__file__)

    # 1. Find all semantic objects
    semantic_objects = [
        obj for obj, cls in classes.items() if cls == "cmca:SemanticObject"
    ]
    semantic_objects.sort()

    if len(semantic_objects) > N_MAX:
        raise ValueError("CMCA_OBJECT_COUNT_EXCEEDED")

    # 2. Map dependencies and business values
    dependencies = {}
    business_values = {}
    for obj in semantic_objects:
        props = properties.get(obj, {})
        dependencies[obj] = props.get("cmca:dependsOn", [])
        business_values[obj] = props.get("cmca:businessValue", 0.0)

    # 3. Recursively compute downstream consequence mass
    consequence_masses = {}
    memo = {}

    def get_consequence_mass(obj, path=None):
        if path is None:
            path = set()
        if obj in memo:
            return memo[obj]
        if obj in path:
            return 0.0
        path.add(obj)
        val = business_values.get(obj, 0.0)
        for dep in dependencies.get(obj, []):
            val += get_consequence_mass(dep, path)
        path.remove(obj)
        memo[obj] = val
        return val

    for obj in semantic_objects:
        consequence_masses[obj] = get_consequence_mass(obj)

    # Automatically discover factor names
    factor_set = set()
    for obj in semantic_objects:
        props = properties.get(obj, {})
        for pred, val in props.items():
            if pred.startswith("cmca:") and pred not in [
                "cmca:dependsOn",
                "cmca:businessValue",
            ]:
                if isinstance(val, (int, float)):
                    factor_set.add(pred)

    factor_set.add("cmca:businessValue")
    factor_names_full = sorted(list(factor_set))
    factor_names_full.append("cmca:downstreamConsequence")  # always computed last

    F = len(factor_names_full)
    if F > F_MAX:
        raise ValueError("CMCA_FACTOR_COUNT_EXCEEDED")

    # 4. Generate object registry lines
    object_registry_lines = []
    for i, obj in enumerate(semantic_objects):
        props = properties.get(obj, {})
        factors = []
        for f_full in factor_names_full:
            if f_full == "cmca:downstreamConsequence":
                val = consequence_masses.get(obj, 0.0)
            else:
                val = props.get(f_full, 0.0)
            factors.append(val)

        factor_strs = [
            f"NonNegativeFixed::from_bits({to_q16_16(val)})" for val in factors
        ]
        obj_local_name = obj.split(":")[-1]

        lines = [
            f"    // {obj_local_name} ({obj})",
            "    PackedSemanticState {",
            f"        id: {i},",
            "        factors: [",
        ]
        for f_str, f_full, f_val in zip(factor_strs, factor_names_full, factors):
            f_name = f_full.split(":")[-1]
            lines.append(f"            {f_str}, // {f_name}: {f_val:.5f}")
        lines.append("        ],")
        lines.append("    },")
        object_registry_lines.append("\n".join(lines))

    # 5. Global ETA
    eta_val = 0.5
    for props in properties.values():
        if "cmca:eta" in props:
            eta_val = props["cmca:eta"]
            break
    eta_q = to_q16_16(eta_val)

    # 6. Measure Heads (K)
    measure_heads = [mh for mh, cls in classes.items() if cls == "cmca:MeasureHead"]
    mh_indices = {
        mh: properties.get(mh, {}).get("cmca:measureIndex", 0) for mh in measure_heads
    }
    sorted_mh = sorted(measure_heads, key=lambda m: (int(mh_indices[m]), m))
    K = len(sorted_mh)
    if K > K_MAX:
        raise ValueError("CMCA_MEASURE_COUNT_EXCEEDED")

    # 7. Lenses (Q)
    lenses = [lens for lens, cls in classes.items() if cls == "cmca:Lens"]
    lens_indices = {
        lens: properties.get(lens, {}).get("cmca:lensIndex", 0) for lens in lenses
    }
    lens_exponents = {
        lens: properties.get(lens, {}).get("cmca:lensExponent", 0.0) for lens in lenses
    }
    sorted_lenses = sorted(lenses, key=lambda l: (int(lens_indices[l]), l))
    Q = len(sorted_lenses)
    if Q > Q_MAX:
        raise ValueError("CMCA_LENS_COUNT_EXCEEDED")

    # 8. Lambda Matrix
    lambda_coeffs = {}
    for coeff_uri, cls in classes.items():
        if cls == "cmca:LambdaCoefficient":
            props = properties.get(coeff_uri, {})
            m_uri = props.get("cmca:measure")
            l_uri = props.get("cmca:lens")
            if not m_uri and "cmca:measureIndex" in props:
                m_idx = int(props["cmca:measureIndex"])
                if m_idx < len(sorted_mh):
                    m_uri = sorted_mh[m_idx]
            if not l_uri and "cmca:lensIndex" in props:
                l_idx = int(props["cmca:lensIndex"])
                if l_idx < len(sorted_lenses):
                    l_uri = sorted_lenses[l_idx]

            val = props.get("cmca:value", 0.0)

            if m_uri in sorted_mh and l_uri in sorted_lenses:
                m_idx = sorted_mh.index(m_uri)
                l_idx = sorted_lenses.index(l_uri)
                lambda_coeffs[(m_idx, l_idx)] = val

    lambda_matrix_lines = []
    for m_idx in range(K):
        row_strs = []
        for l_idx in range(Q):
            val = lambda_coeffs.get((m_idx, l_idx), 0.0)
            row_strs.append(f"NonNegativeFixed::from_bits({to_q16_16(val)})")
        mh_name = sorted_mh[m_idx].split(":")[-1]
        lambda_matrix_lines.append(f"    [{', '.join(row_strs)}], // {mh_name}")

    # 9. Lenses spec lines
    lens_registry_lines = []
    for idx, lens in enumerate(sorted_lenses):
        exp = lens_exponents[lens]
        lens_local = lens.split(":")[-1]
        lens_registry_lines.append(
            f"    // {lens_local} ({lens})\n"
            f"    LensSpec {{ id: {idx}, q: SignedFixed::from_bits({to_q16_16(exp)}) }},"
        )

    # 10. Generate index constants and IRI bindings
    constants_lines = []

    # Digests
    constants_lines.append(f'pub const GENERATOR_VERSION: &str = "v1.1.0";')
    constants_lines.append(f'pub const RDF_INPUT_DIGEST: &str = "{input_digest}";')
    constants_lines.append(
        f'pub const GENERATOR_SOURCE_DIGEST: &str = "{generator_digest}";'
    )

    for i, f_full in enumerate(factor_names_full):
        f_name = f_full.split(":")[-1]
        c_name = "FACTOR_" + re.sub(r"(?<!^)(?=[A-Z])", "_", f_name).upper()
        constants_lines.append(f"pub const {c_name}: usize = {i};")
        constants_lines.append(f'pub const {c_name}_IRI: &str = "{f_full}";')

    for i, mh in enumerate(sorted_mh):
        mh_name = mh.split(":")[-1]
        c_name = re.sub(r"(?<!^)(?=[A-Z])", "_", mh_name).upper()
        constants_lines.append(f"pub const {c_name}: usize = {i};")
        constants_lines.append(f'pub const {c_name}_IRI: &str = "{mh}";')

    for i, lens in enumerate(sorted_lenses):
        lens_name = lens.split(":")[-1]
        c_name = re.sub(r"(?<!^)(?=[A-Z])", "_", lens_name).upper()
        constants_lines.append(f"pub const {c_name}: usize = {i};")
        constants_lines.append(f'pub const {c_name}_IRI: &str = "{lens}";')

    for i, obj in enumerate(semantic_objects):
        obj_name = obj.split(":")[-1]
        c_name = "OBJECT_" + re.sub(r"(?<!^)(?=[A-Z])", "_", obj_name).upper()
        constants_lines.append(f"pub const {c_name}: usize = {i};")
        constants_lines.append(f'pub const {c_name}_IRI: &str = "{obj}";')

    # 11. Write output generated file
    generated_code = f"""// This file is generated by generator.py. DO NOT EDIT.

use crate::fixed::{{NonNegativeFixed, SignedFixed}};

pub const N: usize = {len(semantic_objects)};
pub const F: usize = {F};
pub const K: usize = {K};
pub const Q: usize = {Q};

{chr(10).join(constants_lines)}

#[derive(Copy, Clone, Debug)]
pub struct PackedSemanticState {{
    pub id: u32,
    pub factors: [NonNegativeFixed; F],
}}

#[derive(Copy, Clone, Debug)]
pub struct LensSpec {{
    pub id: u32,
    pub q: SignedFixed,
}}

pub static ETA: NonNegativeFixed = NonNegativeFixed::from_bits({eta_q}); // {eta_val:.5f}

pub static LAMBDA: [[NonNegativeFixed; Q]; K] = [
{chr(10).join(lambda_matrix_lines)}
];

pub static OBJECT_REGISTRY: [PackedSemanticState; N] = [
{chr(10).join(object_registry_lines)}
];

pub static LENS_REGISTRY: [LensSpec; Q] = [
{chr(10).join(lens_registry_lines)}
];
"""

    with open(out_path, "w") as f:
        f.write(generated_code)

    print(
        f"Generated {out_path} successfully (N={len(semantic_objects)}, K={K}, Q={Q}, F={F})."
    )


if __name__ == "__main__":
    main()
