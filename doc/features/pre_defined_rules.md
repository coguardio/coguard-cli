# Pre defined rule-sets

## Default rule set

CoGuard, in its current implementation, comes with a default rule
set. This rule-set is a mix of

- common security benchmarks,
- developer recommendations from the manuals,
- practical experience with pit-falls and
- enforcements application of security best practices as described e.g. by OWASP or CWEs.

The rules are grouped by a severity ranging from 1 (low) to 5
(critical). The rationale behind each group can be summarized in the
following way.

### Severity 1 (Low)

- Linting
- "Nice to have" for extra system logs

### Severity 2 (Moderate Low)

- Performance affecting (slightly)
- Potential for filling up logging and being too loud
- The "are you sure" category
- Potential for too little logging
- Potential for loss of logging control

### Severity 3 (Moderate)

- Settings that are set, but are not taking effect because others are overwriting it. I.e. source of unintentional behavior
- Potentially highly performance affecting
- "High Availability" violations

### Severity 4 (High)

- Data potentially externally available, but high effort needed to access it
- When access to the hosting machine, sensitive information can partially being taken out
- Usually Severity 5, but only available on Enterprise edition
- Available, but too loose access restrictions
- Easily probed by an attacker

### Severity 5 (Critical)
- Data potentially available externally
- Mechanisms for data/disaster recovery/post-incident analysis disabled
- When access to the hosting machine, data can be fully taken out
- If exploitable, data is open or damage can be made

## SOC2

The Trust Services Criteria as defined by the AICPA can be directly
mapped to cluster configurations and policies.

The version used is the 2017 Trust Services Criteria with the March 2020
updates.

The SOC2 rule-set increases the severity of checks that directly relate to trust service
criteria to severity high (4) and critical (5), whereas the other rules are grouped
similar to the the description of the default rule-set at the range
1-3. Additional rules specific to the compliance framework have been
added and will appear as severity 4 or 5, if violated.

## HIPAA

The US Department of Health and Human Services HIPAA Audit protocol
has been used to map relevant rules in the CoGuard database to
paragraphs of the established performance criteria in the Health
Insurance Portability and Accountability Act.

Similar to the SOC2, any rule relevant to HIPAA will have severity 4
or 5, and the other rules are grouped similar to the the description of the default rule-set at the range
1-3. Additional rules specific to the compliance framework have been
added and will appear as severity 4 or 5, if violated.

## Roadmap

- ISO 27001
