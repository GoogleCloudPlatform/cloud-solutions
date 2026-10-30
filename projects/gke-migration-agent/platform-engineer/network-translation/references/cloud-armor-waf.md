# Cloud Armor WAF rule and tuning reference

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

<!--
    Disabling markdownlint MD030 to allow the list overflowing to numbers
    >=10.
-->
<!-- markdownlint-disable MD030 -->

<!-- markdownlint-disable MD013 -->

This reference defines the mapping heuristics, OWASP Core Rule Set (CRS)
versions, paranoia tuning levels, and common CVE pre-filter CEL expressions for
translating AWS WAF Managed Rules to Google Cloud Armor Security Policies.

> [!NOTE]
>
> Both Cloud Armor preconfigured WAF rules and Cloud Armor rule tuning reference
> OWASP CRS lineage, not AWS Managed Rule Groups. The mappings below are
> tool-opinionated heuristics derived from OWASP coverage. Validate against real
> production traffic.

## 1. CRS version selection

Cloud Armor publishes preconfigured rules from three CRS versions:

| CRS Version | Suffix                                   | Notes                                                                                                              |
| :---------- | :--------------------------------------- | :----------------------------------------------------------------------------------------------------------------- |
| **4.22**    | `-v422-stable`, `-v422-canary`           | Recommended default. The `nodejs` rule from v3.3 was reclassified as `generic` in v4.22 (same `934`-prefixed IDs). |
| **3.3**     | `-v33-stable`, `-v33-canary`             | Has separate `java` and `nodejs` rules. Useful for JSON-SQLi pre-filters.                                          |
| **3.0**     | `-stable`, `-canary` (no version suffix) | Legacy. Avoid for new policies.                                                                                    |

Default to v4.22. Choose canary for new tunings and promote to stable after a
soak period.

## 2. AWS WAF managed rule groups mapping decision table

| AWS WAF Managed Group                   | Closest Cloud Armor Preconfigured Rules                                                                                             | Notes                                                   |
| :-------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------ |
| `AWSManagedRulesCommonRuleSet`          | `xss-v422-stable`, `lfi-v422-stable`, `protocolattack-v422-stable`, `scannerdetection-v422-stable`, `methodenforcement-v422-stable` | Common ruleset spans many categories; combine multiples |
| `AWSManagedRulesKnownBadInputsRuleSet`  | `protocolattack-v422-stable`, `scannerdetection-v422-stable`                                                                        | Known-bad inputs and scanners                           |
| `AWSManagedRulesSQLiRuleSet`            | `sqli-v422-stable` (+ `json-sqli-canary` if JSON bodies)                                                                            | See JSON-SQLi pre-filter section below                  |
| `AWSManagedRulesPHPRuleSet`             | `php-v422-stable`                                                                                                                   | PHP attack signatures                                   |
| `AWSManagedRulesUnixRuleSet`            | `rce-v422-stable`, `lfi-v422-stable`                                                                                                | RCE and LFI cover Unix attack surface                   |
| `AWSManagedRulesWindowsRuleSet`         | `rce-v422-stable`                                                                                                                   | No Windows-specific group; RCE covers OS injection      |
| `AWSManagedRulesLinuxRuleSet`           | `rce-v422-stable`, `lfi-v422-stable`                                                                                                | Linux OS injection and file inclusion                   |
| `AWSManagedRulesAnonymousIpList`        | (No 1:1) — use Cloud Armor `origin.region_code` + IP allowlists                                                                     | Heuristic; consider Cloud Armor Adaptive Protection     |
| `AWSManagedRulesAmazonIpReputationList` | (No 1:1) — Adaptive Protection + custom CEL deny                                                                                    | Reputation-based blocking                               |
| `AWSManagedRulesBotControlRuleSet`      | reCAPTCHA Enterprise integration with Cloud Armor                                                                                   | Different UX; surface as design decision                |
| **Custom Regex / String Match**         | CEL expression(s) on the security policy                                                                                            | Translate each rule individually                        |
| **Rate-Based Rules**                    | `rate_limit_options` (`rate_based_ban` or `throttle`)                                                                               | Configured on rule options, not CEL expression          |

## 3. Tuning levels and sensitivity (paranoia)

Sensitivity corresponds to the OWASP CRS paranoia level (`0`–`4`). Lower
sensitivity reduces false positives; higher sensitivity increases protection.
Selecting sensitivity `N` opts in all signatures with sensitivity `<= N`.

CEL syntax:

```cel
evaluatePreconfiguredWaf('sqli-v422-stable', {'sensitivity': 1})
```

Production baseline sensitivity settings:

- `xss-v422-stable` at sensitivity 2.
- `sqli-v422-stable` at sensitivity 2 (enable `json-sqli-canary` if API accepts
  JSON request bodies).
- `lfi-v422-stable`, `rfi-v422-stable`, `rce-v422-stable` at sensitivity 2.
- `protocolattack-v422-stable` at sensitivity 2.
- `methodenforcement-v422-stable` at sensitivity 1.
- `scannerdetection-v422-stable` at sensitivity 1 (sensitivity 3+ produces false
  positive noise).

Opt out specific noisy signatures using `opt_out_rule_ids` rather than dropping
the whole rule set:

```cel
evaluatePreconfiguredWaf('sqli-v422-stable', {
  'sensitivity': 4,
  'opt_out_rule_ids': ['owasp-crs-v042200-id942350-sqli', 'owasp-crs-v042200-id942360-sqli']
})
```

The signature-ID prefix must match the CRS version of the rule set (`v042200`
for v4.22, `v030301` for v3.3, `v030001` for v3.0).

## 4. JSON-SQLi inspection

Request bodies must be JSON-parsed for SQLi to be caught within JSON payloads.
Google recommends combining both rule expressions:

```cel
evaluatePreconfiguredWaf('json-sqli-canary', {'sensitivity': 0, 'opt_in_rule_ids': ['owasp-crs-id942550-sqli']})
||
evaluatePreconfiguredWaf('sqli-v33-stable', {'sensitivity': 2})
```

If the application accepts JSON request bodies to any database-touching backend,
apply both expressions.

## 5. CVE rules and cve-canary pre-filters

`cve-canary` ships canary-only signatures and requires opt-in by signature ID.

| Signature ID                                                          | Sensitivity | Description                                           |
| :-------------------------------------------------------------------- | :---------- | :---------------------------------------------------- |
| `owasp-crs-v030001-id44228-cve`                                       | 1           | Base rule for CVE-2021-44228 / CVE-2021-45046 (Log4j) |
| `owasp-crs-v030001-id144228-cve`                                      | 1           | Google enhancements for bypass / obfuscation          |
| `owasp-crs-v030001-id244228-cve`                                      | 3           | Higher-sensitivity bypass detection                   |
| `owasp-crs-v030001-id344228-cve`                                      | 3           | Base64-encoded bypass detection                       |
| `google-mrs-v202512-id000001-rce` / `google-mrs-v202512-id000002-rce` | n/a         | React RCE; gate behind a request pre-filter           |

React RCE recommended request pre-filter expression:

```cel
(has(request.headers['next-action']) || has(request.headers['rsc-action-id']) ||
 request.headers['content-type'].contains('multipart/form-data') ||
 request.headers['content-type'].contains('application/x-www-form-urlencoded'))
&& evaluatePreconfiguredWaf('cve-canary', {'sensitivity': 0,
   'opt_in_rule_ids': ['google-mrs-v202512-id000001-rce','google-mrs-v202512-id000002-rce']})
```

## 6. Operational constraints

- **Propagation Delay:** Security policy rule updates require several minutes to
  propagate globally across Google Cloud edge proxies.
- **64 KB Payload Limit:** Cloud Armor evaluates preconfigured WAF rules against
  the **first 64 KB** of request bodies. Payloads exceeding 64 KB are not
  inspected end-to-end.
- **JSON Parsing Requirement:** Enable JSON parsing explicitly to inspect JSON
  payload bodies.
- **Rule Action Restrictions:** The `--request-*-to-exclude` parameters (header,
  cookie, query, URI) cannot be applied to rules configured with action `allow`.
- **Adaptive Protection:** Enabled at the security policy level
  (`--enable-layer7-ddos-defense`). ML-suggested rules surface in Cloud Logging
  alerts rather than via inline CEL expressions.
