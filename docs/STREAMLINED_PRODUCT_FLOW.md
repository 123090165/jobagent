# Streamlined Product Flow

## User-Visible Flow

JobAgent presents three product stages:

~~~text
Profile
-> Search Setup
-> Results
~~~

Internal parsing, review, draft, confirmation, mission interpretation, provider
preview, tracing, and analysis remain explicit backend states. They are not all
presented as separate product milestones.

## Search Setup

After profile analysis, Search Setup asks only for factors that materially
change recall or ranking:

- target and excluded roles;
- location constraints;
- must-have conditions;
- ranking priorities;
- focused, balanced, or exploratory search breadth.

Industry, work arrangement, employment type, nice-to-have signals, and free-form
context remain available as optional details. The system interprets the setup
automatically when the user continues. It interrupts the flow only for detected
conflicts or clarification questions; otherwise it proceeds directly to source
selection and presearch preview.

## Analysis Boundary

Search-time analysis is broad and lightweight. It provides evidence-grounded
ranking scores, concise match reasons, major risks, JD quality, and confidence.
It must not grow into resume tailoring, interview preparation, or a detailed
application strategy for every recalled job.

Job Brief is narrow and deep. It runs only for a saved job and converts the JD,
latest search analysis, and selected profile into resume actions, interview
focus, and next steps. Search Analysis decides what deserves attention; Job
Brief decides how to act on a selected opportunity.

## Compatibility Boundary

This UX change does not remove persisted workflow states, Search Mission data,
existing APIs, trace steps, or historical runs. Search Mission remains the
internal structured representation of Search Setup.
