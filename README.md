# US Restricted Party Screening (Apify Actor)

Screen company, vendor, supplier and manufacturer names against five US restricted-party lists that the trade.gov Consolidated Screening List does not carry, and that most default screening setups therefore miss:

| List | What it means for you | Official source |
|---|---|---|
| DoD Chinese Military Companies (Section 1260H), with every named subsidiary | Section 805 of the FY2024 NDAA bars DoD contracts with listed companies from June 30, 2026, and indirect dealings from June 30, 2027 | Federal Register notices from DoD |
| Section 889 (FAR 52.204-25): Huawei, ZTE, Hytera, Hikvision, Dahua and their affiliates | Federal contractors and grantees may not buy or use their telecom and video surveillance gear | eCFR |
| FCC Covered List | No FCC equipment authorization; no Universal Service money for this gear | fcc.gov/supplychain/coveredlist |
| DHS UFLPA Entity List | Goods are presumed made with forced labor and held at the US border | dhs.gov/uflpa-entity-list |
| BIOSECURE biotechnology companies of concern (interim) | Federal agencies may not buy their biotechnology equipment or services, on the Act's phased schedule | derived from the 1260H biotech listings until OMB publishes its list |

Each match comes back with the listed name, the alias it matched, the parent company for a named subsidiary, the listing date and the government source URL, so a reviewer can check it in one click.

## Input

| Field | Default | Notes |
|---|---|---|
| `names` | (required) | One name per line, up to 50,000 per run. Duplicates are screened once. |
| `minScore` | 0.88 | 0.5 to 1.0. 1.0 keeps only exact matches after punctuation and legal suffixes (Co., Ltd., Inc., Group) are removed. |
| `lists` | all five | `US_DOD_1260H`, `US_FAR_889`, `US_FCC_COVERED`, `US_DHS_UFLPA`, `US_BIOSECURE` |
| `maxMatchesPerName` | 3 | Best matches kept per name. |

```json
{ "names": ["Hikvision", "BGI Genomics Co., Ltd.", "Acme Industrial Supply"], "minScore": 0.88 }
```

## Output

One dataset item per name screened:

```json
{
  "input": "Hikvision",
  "hit": true,
  "bestScore": 1.0,
  "matches": [
    {
      "score": 1.0, "matchType": "exact",
      "list": "DoD Chinese Military Companies (Section 1260H)", "dataSource": "US_DOD_1260H",
      "listedName": "Hangzhou Hikvision Digital Technology Co., Ltd.", "matchedName": "Hikvision",
      "parentName": null, "listedOn": "2026-06-10", "includesAffiliates": false,
      "sourceUrl": "https://www.federalregister.gov/documents/2026/06/10/2026-11571/...",
      "sourceDoc": "2026-11571", "recordId": "us_dod_1260h-hangzhou-hikvision-digital-technology-co-ltd"
    },
    { "score": 0.9, "matchType": "contained", "dataSource": "US_FAR_889", "listedName": "Hangzhou Hikvision Digital Technology Company", "includesAffiliates": true }
  ],
  "feedRelease": "data-2026-11-18-1655",
  "feedBuiltAt": "2026-11-18T16:52:41Z"
}
```

The `OUTPUT` record in the run's key-value store has the totals, the lists used and the feed release, for your audit file.

## How matching works

Both names are folded to ASCII, lowercased, and stripped of punctuation and legal suffixes. Then:

- `exact` (score 1.0): the names are equal, including against every alias and former name the listing gives.
- `contained` (0.9): a distinctive name appears whole inside a listed name, such as "Hytera" in "Hytera Communications Corporation". Generic words ("Technology", "China", "Aviation") never make a contained match on their own.
- `similar` (0.5 to 1.0): spelling similarity (Python difflib ratio), for typos and transliterations.

A match is a lead to review against the source, not a legal finding. A name with no match is not a clearance: some listings (`includesAffiliates: true`, for example Section 889) cover affiliates the government does not name, so screen those by ownership too.

## Data

Every run downloads the current release of [US Restricted Parties](https://github.com/Mattbusel/us-restricted-parties), rebuilt daily from the official sources (CC BY 4.0, compiled by Tensorust LLC). Nothing you screen is sent anywhere else: names are matched inside the run, and results stay in your Apify storage.

## Run it locally

```
pip install apify==4.3.0
npm install -g apify-cli
apify run -p -i '{"names": ["Hikvision", "Acme Industrial Supply"]}'
python -m unittest discover -s tests
```

## Support

Issues: https://github.com/Mattbusel/apify-restricted-party-screen/issues. Email: mattbusel@tensorust.com.

Not legal advice. Code: MIT. Data: CC BY 4.0.
