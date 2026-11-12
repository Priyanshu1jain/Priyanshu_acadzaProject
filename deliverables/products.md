# Acadza — Product Thinking

## Who loses the most when a question is broken?

The biggest impact falls on students preparing for high-stakes examinations such as JEE and NEET. A wrong answer key, missing condition, or incorrect solution can waste preparation time, create confusion, and potentially affect a student's performance. The impact is amplified when the same question is served to thousands of students.

Faculty members also lose time manually investigating repetitive reports. Acadza therefore needs a system that reduces investigation effort without sacrificing correctness.

Our design separates **report intent classification** from **question verification**. A student's comment is treated as a lead, not proof. Reports about the same question can be investigated together, while distinct complaints remain individually traceable. Faculty receive the original question, student reports, AI verdict, supporting evidence, and a precise proposed change before making a decision.

## What should AI never auto-apply?

AI should never independently apply a correction when the question is ambiguous, has no valid answer as written, requires new academic content, or needs human interpretation.

In particular, changes involving missing or incorrect diagrams, identical options requiring new distractors, mismatched questions and solutions, unsound questions, and syllabus disputes should remain under faculty control. These are also represented as human-review cases in the supplied taxonomy.

Even for repair types marked as automatically applicable, automation should be conditional on sufficient evidence, a validated edit, and strict field-level restrictions. A confidence score alone is not proof of correctness. If evidence conflicts or the proposed edit exceeds the permitted scope, the system should stop and route the case to faculty.

## One metric to monitor in week one

**Verified auto-fix precision:** the percentage of automatically applied corrections that are confirmed correct during subsequent quality checks.

This is more meaningful than simply counting how many reports the AI processes. A high automation rate is not useful if incorrect corrections reach students. We should also track the number of harmful corrections and treat any such incident as a safety failure requiring investigation.

## One idea beyond the brief

Introduce a **question health and recurrence tracker**. Instead of treating every report as an isolated event, Acadza could maintain a history of defects, student reports, faculty decisions, and repeat incidents for each question.

This would help identify questions that repeatedly generate confusion, detect recurring content-quality problems across chapters, and prioritise preventive reviews before more students are affected.

The long-term goal is not just to resolve reported errors, but to continuously improve the reliability of Acadza's question bank.