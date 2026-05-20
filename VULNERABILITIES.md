Run started:2026-05-20 05:41:11.105744+00:00

Test results:
>> Issue: [B608:hardcoded_sql_expressions] Possible SQL injection vector through string-based query construction.
   Severity: Medium   Confidence: Medium
   CWE: CWE-89 (https://cwe.mitre.org/data/definitions/89.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b608_hardcoded_sql_expressions.html
   Location: src/pyscribe_code/core/graph_db.py:122:37
121	                    placeholders = ",".join("?" * len(node_ids))
122	                    cursor.execute(f"DELETE FROM edges WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})", node_ids + node_ids)
123	                    cursor.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", node_ids)

--------------------------------------------------
>> Issue: [B608:hardcoded_sql_expressions] Possible SQL injection vector through string-based query construction.
   Severity: Medium   Confidence: Medium
   CWE: CWE-89 (https://cwe.mitre.org/data/definitions/89.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b608_hardcoded_sql_expressions.html
   Location: src/pyscribe_code/core/graph_db.py:123:37
122	                    cursor.execute(f"DELETE FROM edges WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})", node_ids + node_ids)
123	                    cursor.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", node_ids)
124

--------------------------------------------------
>> Issue: [B404:blacklist] Consider possible security implications associated with the subprocess module.
   Severity: Low   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_imports.html#b404-import-subprocess
   Location: src/pyscribe_code/managers/sandbox_validator.py:8:0
7	import logging
8	import subprocess
9	import sys

--------------------------------------------------
>> Issue: [B603:subprocess_without_shell_equals_true] subprocess call - check for execution of untrusted input.
   Severity: Low   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html
   Location: src/pyscribe_code/managers/sandbox_validator.py:119:21
118	        try:
119	            result = subprocess.run(
120	                [sys.executable, "-m", "ruff", "check", "--output-format=json", "-"],
121	                input=code,
122	                capture_output=True,
123	                text=True,
124	                timeout=15,
125	            )
126	            if result.stdout.strip():

--------------------------------------------------
>> Issue: [B603:subprocess_without_shell_equals_true] subprocess call - check for execution of untrusted input.
   Severity: Low   Confidence: High
   CWE: CWE-78 (https://cwe.mitre.org/data/definitions/78.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b603_subprocess_without_shell_equals_true.html
   Location: src/pyscribe_code/managers/sandbox_validator.py:165:21
164
165	            result = subprocess.run(
166	                [sys.executable, "-m", "mypy", temp_path, "--no-error-summary"],
167	                capture_output=True,
168	                text=True,
169	                timeout=10,
170	            )
171	            for line in result.stdout.strip().split("\n"):

--------------------------------------------------
>> Issue: [B110:try_except_pass] Try, Except, Pass detected.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/plugins/b110_try_except_pass.html
   Location: src/pyscribe_code/managers/skill_manager.py:211:20
210	                            description = self._extract_description_from_content(content)
211	                    except Exception:
212	                        pass
213

--------------------------------------------------
>> Issue: [B311:blacklist] Standard pseudo-random generators are not suitable for security/cryptographic purposes.
   Severity: Low   Confidence: High
   CWE: CWE-330 (https://cwe.mitre.org/data/definitions/330.html)
   More Info: https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_calls.html#b311-random
   Location: src/pyscribe_core/retry.py:42:33
41	                    if jitter:
42	                        delay *= random.uniform(0.5, 1.5)
43

--------------------------------------------------

Code scanned:
	Total lines of code: 2517
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 0

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 5
		Medium: 2
		High: 0
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 2
		High: 5
Files skipped (0):
