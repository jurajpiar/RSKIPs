"""Survey update of the change-vs-payload model (RSKIP ZZZ). Standard library only.
Loss = probability that a flagged deposit ends with the payer not made whole (automatically).
Advantage = loss(payload refund, flags 01) minus loss(change refund, flags 03); positive favours the change output."""
import math, random, statistics
random.seed(20261118)
N = 200_000
U = random.uniform
B = random.betavariate
LU = lambda a, b: math.exp(U(math.log(a), math.log(b)))
def LN(med, hi97): return min(0.999, math.exp(random.gauss(math.log(med), math.log(hi97 / med) / 1.8808)))
def hdi(xs, mass=0.94):
    xs = sorted(xs); n = len(xs); k = int(mass * n)
    i = min(range(n - k), key=lambda j: xs[j + k] - xs[j]); return xs[i], xs[i + k]
def q(xs, p): xs = sorted(xs); return xs[int(p * (len(xs) - 1))]
def summ(xs, pct=True):
    s = 100 if pct else 1; lo, hi = hdi(xs)
    return f"median {statistics.median(xs)*s:.2f} mean {statistics.mean(xs)*s:.2f} [94% HDI {lo*s:.2f}, {hi*s:.2f}]"
def lr_odds(p, lo, hi):          # multiply the odds of p by a likelihood ratio drawn log-uniformly from [lo, hi]
    o = p / (1 - p) * LU(lo, hi); return o / (1 + o)

# ---------------------------------------------------------------- measured inputs (survey, n = 822 mainnet peg-ins)
RSKT_RECENT = (149, 451)   # payload-carrying deposits 2024-2026 that do NOT have exactly one other output
RSKT_ALL    = (170, 703)
RSKT_2023   = (21, 252)
RSKT_2026   = (41, 92)
MISMATCH    = (8, 533)     # payload-carrying, single other output whose script type differs from every input's
W_NOADDR    = (154, 170)   # rule-breaking payload deposits with a native segwit/taproot input (no sender-derived address)
CONST_REF   = (117, 335)   # refund fields carrying one constant address used by 62 distinct input addresses
DESIGN      = 4.0          # design effect: deposits cluster by composer, wallet and period; flagged composers may differ

# ---------------------------------------------------------------- parameter samplers
def z_post(kn=RSKT_RECENT, D=DESIGN, a0=2, b0=10):
    k, n = kn; return B(a0 + k / D, b0 + (n - k) / D)
def ec_post_sampler(M=400_000):
    """e_c: honest error, the single other output is not the payer's. Prior LU(0.1%, 3%).
    Likelihood: 8 of 533 single other outputs have a script type unlike every input. P(type differs) = e_c*a + (1-e_c)*b,
    a = P(differs | not the payer's) ~ U(0.3, 0.9) [non-payload group: 70% differ], b = P(differs | payer's own) ~ U(0, 3%), a flat nuisance: the data bound e_c, they do not measure it."""
    k, n = MISMATCH[0] / DESIGN, MISMATCH[1] / DESIGN; pool, wts = [], []   # the 8 are one pattern (taproot inputs, P2SH other)
    for _ in range(M):
        e, a, b = LU(0.001, 0.03), U(0.3, 0.9), U(0.0, 0.03)
        p = e * a + (1 - e) * b
        pool.append(e); wts.append(math.exp(k * math.log(p) + (n - k) * math.log(1 - p)))
    return pool, wts
EC_POOL, EC_W = ec_post_sampler()
ess = sum(EC_W) ** 2 / sum(w * w for w in EC_W)

def draw_prior():
    return dict(rho=U(0.02, 0.30), h=LU(0.0005, 0.02), d_f=U(0.0, 0.20), d_c=U(0.25, 0.90),
                e_f=LU(0.002, 0.05), e_c=LU(0.001, 0.03), g=LU(0.001, 0.05), w=U(0.50, 0.95))

def draw_post(u=None, v=None, carry="mid", zkn=RSKT_RECENT, u_med=0.03, u_hi=0.20):
    p = dict(rho=U(0.02, 0.30), h=LU(0.0005, 0.02), d_f=U(0.0, 0.20))
    # --- z: P(not exactly one other output) for a composer that ignores the rule. Prior Beta(2,10) (changeless payments in general)
    p["z"] = z_post(zkn)
    # --- u: share of flags-03 deposits whose composer does not check the rule before signing
    if u is None:
        u0 = LN(u_med, u_hi)                      # prior: median 3%, 97th percentile 20%
        u0 = lr_odds(u0, 0.6, 1.0)                # E: the official app builds payload and selects coins in one place (can check); weak, new composers differ
        u0 = lr_odds(u0, 1.0, 1.5)                # E: under the adopted rule a broken rule is silent whenever the destination has code
        p["u"] = u0
    else: p["u"] = u
    p["s"] = LU(0.0002, 0.01)                     # slip rate of a composer that does check (bugs, races); not informed by the survey
    p["g"] = p["u"] * p["z"] + (1 - p["u"]) * p["s"]
    # --- v: share of flagged deposits signed in a flow where the signing wallet itself verifies the change as its own
    p["v"] = B(3, 4) if v is None else v          # prior Beta(3,2); survey: 0 of 3 signing integrations of ONE app verify, counted as 2
    p["d_v"], p["d_n"] = U(0.50, 0.90), U(0.05, 0.35)
    p["d_c"] = p["v"] * p["d_v"] + (1 - p["v"]) * p["d_n"]
    # --- e_c: resampled posterior
    p["e_c"] = random.choices(EC_POOL, EC_W)[0] if False else None
    # --- e_f: prior LU(0.2%, 5%) plus carry-over of the measured habit of writing a constant, non-payer refund address
    e0 = LU(0.002, 0.05)
    if carry == "mid": e0 = min(0.5, e0 * LU(1.0, 2.5))   # central: the measured habit raises the base rate by a factor 1 to 2.5
    if carry == "strong":
        c1 = B(CONST_REF[0] + 0.5, CONST_REF[1] - CONST_REF[0] + 0.5)   # share of refund fields with the constant today (v1)
        keep = U(0.01, 0.15)                      # P(such a composer still writes a non-payer address when v3 can encode the payer's)
        share = U(0.3, 0.9)                       # share of flagged deposits coming from composers of this kind
        p["c3"] = c1 * keep * share
    else: p["c3"] = 0.0
    p["e_f"] = e0 + (1 - e0) * p["c3"]
    p["w"] = B(W_NOADDR[0] / DESIGN + 1, (W_NOADDR[1] - W_NOADDR[0]) / DESIGN + 1)
    return p

def fill_ec(S):
    ecs = random.choices(EC_POOL, EC_W, k=len(S))
    for p, e in zip(S, ecs): p["e_c"] = e
    return S

def losses(p):
    cp = (1 - p["h"]) * p["e_f"] + p["h"] * (1 - p["d_f"])       # payload refund misses the payer | refund due
    cc = (1 - p["h"]) * p["e_c"] + p["h"] * (1 - p["d_c"])       # change refund misses the payer | refund due, deposit has change
    L01 = p["rho"] * cp
    L03_draft   = p["g"] * p["w"] + (1 - p["g"]) * p["rho"] * cc            # first draft: broken rule = parse failure
    L03_old_c   = p["g"] * p["w"] * p["rho"] + (1 - p["g"]) * p["rho"] * cc # earlier pass's variant (c), kept w by mistake
    L03_adopted = p["g"] * p["rho"] + (1 - p["g"]) * p["rho"] * cc          # adopted: no change + no code = unrefundable (7), no release
    return dict(a=cp - cc, a2=cp - (p["g"] + (1 - p["g"]) * cc), draft=L01 - L03_draft, oldc=L01 - L03_old_c,
                adopted=L01 - L03_adopted, L01=L01, L03=L03_adopted, cp=cp, cc=cc)

def rep(label, d):
    lo, hi = hdi(d)
    print(f"   {label:<74} P(change better) {sum(x > 0 for x in d)/len(d):.2f}; advantage median {statistics.median(d)*100:+.3f} pp "
          f"[{lo*100:+.3f}, {hi*100:+.3f}], mean {statistics.mean(d)*100:+.3f}")

print("=" * 110, "\n1. PARAMETERS: prior -> posterior (percent, 94% HDI)\n")
P0 = [draw_prior() for _ in range(N)]
S = fill_ec([draw_post() for _ in range(N)])
S_nc = fill_ec([draw_post(carry="off") for _ in range(N)])
S_st = fill_ec([draw_post(carry="strong") for _ in range(N)])
zp = [B(2, 10) for _ in range(N)]
print(f"z   P(not exactly one other output | composer ignores the rule)\n      prior Beta(2,10): {summ(zp)}\n      post  (payload deposits 2024-26, 149/451, design effect {DESIGN:.0f}): {summ([p['z'] for p in S])}")
for lab, kn in (("all payload deposits 170/703", RSKT_ALL), ("2023 only 21/252", RSKT_2023), ("2026 only 41/92", RSKT_2026)):
    print(f"      alt   ({lab}): {summ([z_post(kn) for _ in range(50_000)])}")
up = [LN(0.03, 0.20) for _ in range(N)]
print(f"u   share of flags-03 deposits from composers that do not check the rule\n      prior lognormal(median 3%, 97th pct 20%): {summ(up)}\n      post  (LR 0.6-1.0 single composer; LR 1.0-1.5 silent failure): {summ([p['u'] for p in S])}")
print(f"s   slip rate of a checking composer: LU(0.02%, 1%), unchanged: {summ([p['s'] for p in S])}")
print(f"g   P(a flags-03 deposit breaks the rule) = u*z + (1-u)*s\n      prior LU(0.1%, 5%): {summ([p['g'] for p in P0])}\n      post : {summ([p['g'] for p in S])}")
vp = [B(3, 2) for _ in range(N)]
print(f"v   share of flagged deposits where the signing wallet verifies change as its own\n      prior Beta(3,2): {summ(vp)}\n      post  Beta(3,4) (0 of 3 signing integrations of the official app, counted as 2 observations): {summ([p['v'] for p in S])}")
print(f"d_c P(payer notices a substituted change output) = v*U(50,90%) + (1-v)*U(5,35%)\n      prior U(25%, 90%): {summ([p['d_c'] for p in P0])}\n      post : {summ([p['d_c'] for p in S])}")
print(f"d_f P(payer notices a substituted refund field): U(0, 20%) unchanged: {summ([p['d_f'] for p in S])}")
print(f"e_c honest error, the single other output is not the payer's\n      prior LU(0.1%, 3%): {summ([p['e_c'] for p in P0])}\n      post  (8/533 type mismatches, design effect 4, flat nuisance; importance sampling, ESS {ess:,.0f}): {summ([p['e_c'] for p in S])}")
print(f"e_f honest error, the refund field names an address the payer cannot use\n      prior LU(0.2%, 5%): {summ([p['e_f'] for p in P0])}\n      post  central (prior x LU(1, 2.5)): {summ([p['e_f'] for p in S])}\n      alt   no shift: {summ([p['e_f'] for p in S_nc])}\n      alt   strong carry-over (117/335 x keep U(1,15%) x share U(30,90%) added): {summ([p['e_f'] for p in S_st])}")
print(f"w   P(no sender-derived address | rule broken) (first-draft rule only)\n      prior U(50%, 95%): {summ([p['w'] for p in P0])}\n      post  (154/170, design effect {DESIGN:.0f}): {summ([p['w'] for p in S])}")
print("rho, h: unchanged (rho U(2%,30%), h LU(0.05%,2%)); the survey does not inform them")

print("\n" + "=" * 110, "\n2. RESULTS\n")
R0 = [losses(p) for p in P0]; R = [losses(p) for p in S]; Rn = [losses(p) for p in S_nc]; Rs = [losses(p) for p in S_st]
print("Earlier pass (priors), reproduced:")
rep("(a) refund reaches the payer | refund due, deposit has change", [r["a"] for r in R0])
rep("(c) per flagged deposit, as computed then (loss g*w*rho)", [r["oldc"] for r in R0])
rep("    same, corrected: adopted rule builds no release, so w = 1", [r["adopted"] for r in R0])
print("\nAfter the survey, central (e_f raised by a factor 1 to 2.5):")
rep("(a)  refund reaches the payer | refund due, deposit has change", [r["a"] for r in R])
rep("(a') refund reaches the payer | refund due (includes deposits without change)", [r["a2"] for r in R])
rep("(b)  per flagged deposit, adopted rule", [r["adopted"] for r in R])
rep("     per flagged deposit, first-draft rule (parse failure)", [r["draft"] for r in R])
print(f"     median loss per flagged deposit: payload {statistics.median(r['L01'] for r in R)*100:.3f} pp; change (adopted) {statistics.median(r['L03'] for r in R)*100:.3f} pp;"
      f" means {statistics.mean(r['L01'] for r in R)*100:.3f} vs {statistics.mean(r['L03'] for r in R)*100:.3f} pp")
print("\nAfter the survey, STRONG e_f carry-over:")
rep("(a)  refund reaches the payer | refund due, deposit has change", [r["a"] for r in Rs])
rep("(b)  per flagged deposit, adopted rule", [r["adopted"] for r in Rs])
print("\nAfter the survey, e_f NOT shifted (stays at its prior):")
rep("(a)  refund reaches the payer | refund due, deposit has change", [r["a"] for r in Rn])
rep("(a') refund reaches the payer | refund due (includes deposits without change)", [r["a2"] for r in Rn])
rep("(b)  per flagged deposit, adopted rule", [r["adopted"] for r in Rn])

print("\nWhat moved (a): one-at-a-time, starting from the earlier priors")
def oat(label, **swap):
    d = []
    for p0, p1 in zip(P0[:80_000], S[:80_000]):
        p = dict(p0); p.update({k: p1[k] for k in swap}); d.append(losses(p)["a"])
    rep(label, d)
oat("d_c only", d_c=1); oat("e_c only", e_c=1); oat("e_f only", e_f=1)
print("What moved (b, adopted rule, w = 1): one-at-a-time")
def oatb(label, **swap):
    d = []
    for p0, p1 in zip(P0[:80_000], S[:80_000]):
        p = dict(p0); p.update({k: p1[k] for k in swap}); d.append(losses(p)["adopted"])
    rep(label, d)
oatb("g only", g=1); oatb("e_f only", e_f=1); oatb("d_c and e_c only", d_c=1, e_c=1)

print("\nBreak-even (adopted rule): change equals payload when g = (cp - cc)/(1 - cc)")
gs = [(r["cp"] - r["cc"]) / (1 - r["cc"]) for r in R]; us = [max(0.0, (g_ - p["s"]) / (p["z"] - p["s"])) for g_, p in zip(gs, S)]
print(f"   g* : {summ(gs)}\n   u* (share of non-checking composers at break-even, 0 if g* < s): {summ(us)}")
gs = [(r["cp"] - r["cc"]) / (1 - r["cc"]) for r in Rn]; us = [max(0.0, (g_ - p["s"]) / (p["z"] - p["s"])) for g_, p in zip(gs, S_nc)]
print(f"   e_f not shifted: g* {summ(gs)}\n                           u* {summ(us)}")
med = {k: statistics.median(p[k] for p in S) for k in ("rho", "h", "d_f", "d_c", "e_f", "e_c", "z", "s", "u", "g")}
print("   posterior medians: " + ", ".join(f"{k}={v:.4f}" for k, v in med.items()))

print("\n" + "=" * 110, "\n3. SENSITIVITY\n")
M = 40_000
def cell(key="adopted", **kw):
    d = [losses(p)[key] for p in fill_ec([draw_post(**kw) for _ in range(M)])]
    return sum(x > 0 for x in d) / M, statistics.median(d) * 100
US = (0.0, 0.002, 0.005, 0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 1.0); VS = (0.0, 0.25, 0.5, 0.75, 1.0)
print("3a. (b) per flagged deposit, adopted rule: P(change better) / median advantage in pp.  Rows: u; columns: v")
print("      u \\ v   " + "".join(f"{v:>16.2f}" for v in VS))
for u in US:
    print(f"   {u*100:6.1f} %  " + "".join("   {:.2f} / {:+.3f}".format(*cell(u=u, v=v)) for v in VS))
print("\n3b. Same, e_f not shifted")
for u in US:
    print(f"   {u*100:6.1f} %  " + "".join("   {:.2f} / {:+.3f}".format(*cell(u=u, v=v, carry="off")) for v in VS))
print("\n3c. (a) refund reaches the payer | refund due, deposit has change, by v (u does not enter)")
for c in ("off", "mid", "strong"):
    print(f"   e_f {c:<6}: " + "".join("  v={:.2f}: {:.2f} / {:+.3f}".format(v, *cell(key='a', v=v, carry=c)) for v in VS))
print("\n3d. (a) with a larger hostile share (h 1-10 %), where v matters most")
def cell_h(v, carry):
    d = []
    for p in fill_ec([draw_post(v=v, carry=carry) for _ in range(M)]):
        p["h"] = U(0.01, 0.10); d.append(losses(p)["a"])
    return sum(x > 0 for x in d) / M, statistics.median(d) * 100
for c in ("off", "mid", "strong"):
    print(f"   e_f {c:<6}: " + "".join("  v={:.2f}: {:.2f} / {:+.3f}".format(v, *cell_h(v, c)) for v in VS))
print("\n3e. (b) under other priors on u (median, 97th percentile) and other choices of z")
for lab, kw in (("u prior median 1%, 97th 10%", dict(u_med=0.01, u_hi=0.10)), ("u prior median 3%, 97th 20% (base)", {}),
                ("u prior median 10%, 97th 40%", dict(u_med=0.10, u_hi=0.40)), ("z from all payload deposits (24%)", dict(zkn=RSKT_ALL)),
                ("z from 2023 only (8%)", dict(zkn=RSKT_2023)), ("z from 2026 only (45%)", dict(zkn=RSKT_2026))):
    a = cell(**kw); b = cell(carry="off", **kw)
    print(f"   {lab:<40} e_f central: {a[0]:.2f} / {a[1]:+.3f}    e_f not shifted: {b[0]:.2f} / {b[1]:+.3f}")
print("\n3f. Claim C: 'in a typical flagged deposit the signing wallet checks that the change belongs to it'")
for lab, a, b in (("prior Beta(3,2)", 3, 2), ("sceptical prior Beta(2,2)", 2, 2), ("confident prior Beta(8,2)", 8, 2)):
    pri = [B(a, b) for _ in range(M)]; po = [B(a, b + 3) for _ in range(M)]; po2 = [B(a, b + 1) for _ in range(M)]; pom = [B(a, b + 2) for _ in range(M)]
    print(f"   {lab:<26} P(v > 0.5): prior {sum(x > .5 for x in pri)/M:.2f} -> post {sum(x > .5 for x in po)/M:.2f} (3 integrations as independent), {sum(x > .5 for x in po2)/M:.2f} (as one), {sum(x > .5 for x in pom)/M:.2f} (as two, used);"
          f" mean v {statistics.mean(pri):.2f} -> {statistics.mean(po):.2f} / {statistics.mean(po2):.2f} / {statistics.mean(pom):.2f}")
