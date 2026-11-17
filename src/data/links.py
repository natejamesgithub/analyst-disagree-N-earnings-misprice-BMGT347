"""Point-in-time WRDS link validation and deterministic resolution."""

from .common import identifiers, intervals, numbers, read_csv, validate

IBES_LINKS = ("ticker", "permno", "sdate", "edate", "score")
CCM_LINKS = ("gvkey", "lpermno", "linkdt", "linkenddt", "linktype", "linkprim")


def load(directory, study):
    ibes = read_csv(directory, "ibes_crsp_link", IBES_LINKS)
    identifiers(ibes, "ibes_crsp_link", ("ticker",))
    ibes["ticker"] = ibes["ticker"].str.upper()
    numbers(ibes, "ibes_crsp_link", "permno", integer=True, minimum=1)
    numbers(ibes, "ibes_crsp_link", "score", integer=True, minimum=0)
    validate(ibes, "ibes_crsp_link", "score", ibes["score"].le(6))
    intervals(ibes, "ibes_crsp_link", "sdate", "edate")

    ccm = read_csv(directory, "ccm_link", CCM_LINKS)
    identifiers(ccm, "ccm_link", ("gvkey", "linktype", "linkprim"))
    validate(ccm, "ccm_link", "gvkey", ccm["gvkey"].str.fullmatch(r"\d{1,6}"))
    ccm["gvkey"] = ccm["gvkey"].str.zfill(6)
    numbers(ccm, "ccm_link", "lpermno", integer=True, nullable=True, minimum=0)
    intervals(ccm, "ccm_link", "linkdt", "linkenddt")
    eligible = (
        ccm["lpermno"].gt(0) & ccm["linktype"].str.upper().isin(["LC", "LU"])
        & ccm["linkprim"].str.upper().isin(["P", "C"])
    )
    return ibes[ibes["score"].le(study.max_ibes_score)].drop_duplicates(), ccm[eligible].drop_duplicates()


def active(frame, when, start, end):
    return frame[(frame[start].isna() | frame[start].le(when)) &
                 (frame[end].isna() | frame[end].ge(when))]


def ibes_match(frame, when):
    if frame is None:
        return None, None, "no_ibes_link"
    current = active(frame, when, "sdate", "edate")
    if current.empty:
        return None, None, "no_ibes_link"
    score = current["score"].min()
    permnos = current.loc[current["score"].eq(score), "permno"].unique()
    if len(permnos) != 1:
        return None, score, "ambiguous_ibes_link"
    return permnos[0], score, "matched"


def ccm_match(frame, when):
    if frame is None:
        return None, "no_ccm_link"
    current = active(frame, when, "linkdt", "linkenddt")
    gvkeys = current["gvkey"].unique()
    if len(gvkeys) > 1:
        return None, "ambiguous_ccm_link"
    if len(gvkeys) == 0:
        return None, "no_ccm_link"
    return gvkeys[0], "matched"
