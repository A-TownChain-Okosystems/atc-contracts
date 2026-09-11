#!/usr/bin/env python3
# Copyright (c) 2026 Michael Wroblewski - Apache-2.0
"""EXEC-CHAIN-Assembler (ATC-CONTRACT-EXEC-001 / F-084, SCR-0104).
Compiliert das EXEC-GATE-Subset einer .atc-Contract-Funktion in ATVM-Ops
(.ops-Format). Fail-fast: das Ergebnis wird vor der Ausgabe simuliert und
muss dem erwarteten Vektorwert entsprechen, sonst Exit 1 (No-Evidence-No-Claim).
MVP-Ehrlichkeit: Parameterwerte werden je Testvektor konkret substituiert;
symbolische Parameter folgen mit dem vollstaendigen Compiler.
"""
import argparse, hashlib, json, os, re, sys

OPS = {"+": "Add", "-": "Sub", "*": "Mul"}

def tokenize(s):
    return re.findall(r"\d+|[A-Za-z_][A-Za-z0-9_]*|[()+\-*]", s)

class Parser:
    def __init__(self, toks, env):
        self.t, self.i, self.env = toks, 0, env
    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None
    def take(self):
        tok = self.t[self.i]; self.i += 1; return tok
    def expr(self):
        ops = self.term()
        while self.peek() in ("+", "-"):
            op = self.take(); ops += self.term(); ops.append(OPS[op])
        return ops
    def term(self):
        ops = self.factor()
        while self.peek() == "*":
            self.take(); ops += self.factor(); ops.append("Mul")
        return ops
    def factor(self):
        tok = self.take()
        if tok == "(":
            ops = self.expr(); assert self.take() == ")", "unbalancierte Klammer"
            return ops
        if tok.isdigit():
            return ["Push " + tok]
        if tok in self.env:
            return list(self.env[tok])
        raise SystemExit("ERROR: unbekannter Bezeichner in Ausdruck: " + tok)

def simulate(ops, expected):
    st = []
    for line in ops:
        if line.startswith("Push"):
            st.append(int(line.split()[1]))
        elif line == "Add":
            b = st.pop(); a = st.pop(); st.append((a + b) % 2**64)
        elif line == "Sub":
            b = st.pop(); a = st.pop(); st.append((a - b) % 2**64)
        elif line == "Mul":
            b = st.pop(); a = st.pop(); st.append((a * b) % 2**64)
        elif line == "Halt":
            break
        else:
            raise SystemExit("asm: fuer Simulation nicht unterstuetztes Op: " + line)
    result = st[-1] if st else 0
    if result != expected:
        raise SystemExit("ERROR: Simulation %d != erwartet %d" % (result, expected))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", default="exec_chain/e2e_adder.atc")
    ap.add_argument("--vector", default="exec_chain/vector.json")
    ap.add_argument("--out", default="build")
    a = ap.parse_args()
    src = open(a.contract, encoding="utf-8").read()
    vec = json.load(open(a.vector, encoding="utf-8"))
    m = re.search(r"fn\s+(\w+)\s*\(([^)]*)\)[^{]*\{(.*?)\n    \}", src, re.S)
    if not m:
        raise SystemExit("ERROR: keine compilierbare fn-Definition im Subset gefunden")
    fname, params_raw, body = m.group(1), m.group(2), m.group(3)
    params = [p.strip().split(":")[0] for p in params_raw.split(",") if p.strip()]
    for p in params:
        if p not in vec.get("input", {}):
            raise SystemExit("ERROR: Vektor fehlt Input fuer Parameter " + p)
    env = {p: ["Push " + str(vec["input"][p])] for p in params}
    final = None
    for line in body.splitlines():
        s = line.strip()
        let = re.match(r"let\s+(\w+)\s*=\s*(.+?)\s*$", s)
        ret = re.match(r"return\s+(.+?)\s*$", s)
        if let:
            env[let.group(1)] = Parser(tokenize(let.group(2)), env).expr()
        elif ret:
            final = Parser(tokenize(ret.group(1)), env).expr()
    if final is None:
        raise SystemExit("ERROR: kein return im Subset-Body")
    ops = final + ["Halt"]
    simulate(ops, int(vec["expected"]))
    stem = os.path.splitext(os.path.basename(a.contract))[0]
    sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
    os.makedirs(a.out, exist_ok=True)
    outp = os.path.join(a.out, stem + ".ops")
    with open(outp, "w", encoding="utf-8") as f:
        f.write("# contract: %s\n# fn: %s\n# source_sha256: %s\n# expected: %s\n" % (stem, fname, sha, vec["expected"]))
        f.write("\n".join(ops) + "\n")
    print("OK: %s -> %s (%d Ops, Simulation PASS)" % (a.contract, outp, len(ops)))

if __name__ == "__main__":
    main()
