Design a modern, enterprise-grade web application interface for a Document Data Quality Evaluation Tool.

This tool evaluates the quality of a single uploaded document and presents a detailed quality dashboard immediately after upload.

There is:

No login

No multi-page navigation

No user accounts

No history view (for now)

This is a single-page application with two states:

Initial Upload State

Evaluation Dashboard State

The design must look like a serious enterprise SaaS tool used by data teams, compliance teams, audit teams, or operations teams.

The visual tone must communicate:

Precision

Trust

Intelligence

Professionalism

Data reliability

Avoid playful, cartoonish, or startup-style casual design.

🔷 DESIGN STYLE REQUIREMENTS
Overall Style

Clean enterprise SaaS aesthetic

Inspired by tools like:

Stripe Dashboard

Datadog

Linear

Notion (minimal but structured)

Azure Portal (clean data-focused)

Design Principles

Clear hierarchy

Strong grid system

Structured spacing

Minimal visual noise

Focus on data clarity

Subtle shadows only

Rounded corners but not too soft (6–10px)

Use whitespace intelligently

🔷 COLOR SYSTEM

Use a professional color palette.

Primary Color

Deep blue:

#1E3A8A or similar

Accent Colors for Metrics

Green (Good quality): #16A34A

Yellow (Warning): #EAB308

Red (Critical): #DC2626

Neutral gray text: #6B7280

Light background gray: #F9FAFB

Card background: white

No gradients.
No flashy colors.
No neon tones.

🔷 TYPOGRAPHY

Use a professional sans-serif font:

Inter

SF Pro

Helvetica Neue

Or similar modern clean font

Hierarchy:

H1 – 32px – Bold
H2 – 24px – Semi-bold
H3 – 18px – Medium
Body – 14–16px – Regular
Caption – 12px – Light

Spacing must be consistent.

🔷 LAYOUT STRUCTURE

Use a centered layout with max width of 1200px.

Main page structure:

Header
Main Content Area

Use a 12-column grid.

Padding left and right: 80px
Vertical spacing between sections: 48px

🔷 STATE 1: INITIAL UPLOAD SCREEN

Design the landing state before document upload.

HEADER

Top left:
Logo placeholder (simple geometric icon)

Top right:
Small text:
"Document Quality Evaluation"

Header should be minimal and not distract from upload.

MAIN HERO SECTION

Centered vertically and horizontally.

Large title:

"Evaluate Your Document Data Quality"

Subtitle below:

"Upload a document to receive a structured quality analysis across completeness, accuracy, consistency, validity, timeliness, and uniqueness."

Spacing between title and subtitle: 16px

UPLOAD COMPONENT

Design a large upload card centered.

Card width: 600px
Height: 260px
Border: dashed 2px
Border color: light gray
Rounded corners: 12px

Inside:

Centered upload icon
Text:

"Drag & drop your document here"

Below:

"or click to browse"

Below that:

Supported formats:
PDF, DOCX, PNG, JPG

Below that:

Max file size: 5MB

BUTTON

Primary button:

"Evaluate Document"

Disabled until file selected.

Style:

Background: Primary Blue

Text: White

Height: 44px

Border radius: 8px

LOADING STATE

When evaluating:

Replace button with:

Loading spinner
Text:
"Analyzing document quality..."

Subtext:
"This may take a few seconds"

Minimal animation.

🔷 STATE 2: QUALITY DASHBOARD

After evaluation completes, transform page into dashboard.

Layout must feel structured and analytical.

SECTION 1: OVERALL SCORE CARD

Full-width card at top.

White background
Soft shadow
Padding: 32px

Inside:

Left side:

Large circular score indicator:

Circle with border thickness 10px
Color changes based on score:

90 = Green
70–90 = Yellow
< 70 = Red

Inside circle:

Large number:
"82"

Below number:
"/100"

Right side of card:

Title:
"Overall Document Quality Score"

Below that:

Short explanation:

"This score represents the aggregated evaluation across all defined data quality dimensions."

Below that:

Status badge:

Green badge:
"Good Quality"

Yellow badge:
"Moderate Quality"

Red badge:
"Critical Issues Detected"

SECTION 2: METRICS GRID

Below overall card.

Title:
"Quality Breakdown"

Use 3-column grid (responsive).

Each metric gets its own card.

Total 6 metric cards:

Completeness

Accuracy

Consistency

Validity

Timeliness

Uniqueness

METRIC CARD DESIGN

White background
Rounded corners: 10px
Padding: 24px
Height: consistent

Top left:

Metric name (H3)

Top right:

Small colored percentage badge:
"85%"

Color-coded based on performance.

Below:

Horizontal progress bar:
Full width
Background light gray
Fill color based on metric status

Below:

Short explanation text:

Example for Completeness:

"8 out of 10 required fields were successfully extracted."

Below:

Status message:

"2 required fields are missing."

Or:

"All required fields are present."

Each metric card must have:

Score

What it measures (short sentence)

Quick reasoning

Status indicator

SECTION 3: DETAILED ISSUES TABLE

Below metrics grid.

Title:
"Issues & Observations"

White card
Full width

Table design:

Columns:

Field Name
Issue Type
Description
Severity

Severity badge:

Green – Minor
Yellow – Moderate
Red – Critical

Rows example:

Invoice Date | Missing Field | Required field not detected | Critical
Total Amount | Inconsistent Value | Line items do not match total | Moderate

Table must look clean and structured.

No heavy borders.

Use light dividers.

SECTION 4: METRIC EXPLANATION PANEL

Expandable section.

Title:
"How We Evaluate Document Quality"

Accordion style.

When expanded:

Explain each metric in detail:

Completeness:
Measures whether all required structured fields are present.

Accuracy:
Evaluates extracted data against validation logic and known constraints.

Consistency:
Checks logical relationships between fields.

Validity:
Ensures values conform to expected formats.

Timeliness:
Assesses recency of time-sensitive fields.

Uniqueness:
Identifies duplicate structured entries.

Design this as clean structured paragraphs.

🔷 RESPONSIVE DESIGN

Desktop first.

Tablet:

Metrics grid becomes 2 columns.

Mobile:

Single column stacked.

Upload component scales to full width.

🔷 INTERACTION DESIGN

Hover effects:

Cards slightly elevate

Buttons darken slightly

Table rows highlight on hover

Transitions:

Subtle fade-in when dashboard appears.

No excessive animation.

🔷 EMPTY STATES

If no issues:

Display:

Green check icon
Text:
"No issues detected. Document quality is high."

If evaluation fails:

Red alert box:
"Unable to evaluate document. Please try again."

🔷 FOOTER

Minimal footer:

Left:
"Document Quality Engine v1.0"

Right:
"Powered by AI-assisted evaluation"

Light gray text.

🔷 UX PRINCIPLES

The UI must:

Feel trustworthy

Make scores immediately visible

Make issues easy to identify

Avoid overwhelming users

Focus on clarity over decoration

No dark theme (for now).

🔷 SPACING SYSTEM

Use consistent spacing:

8px base system.

8
16
24
32
48

Vertical rhythm must be consistent.

🔷 COMPONENT LIST

Design reusable components:

Upload Card

Score Circle

Metric Card

Progress Bar

Status Badge

Issue Table Row

Accordion Section

Alert Box

Button (Primary & Secondary)

🔷 VISUAL MOOD

The product should feel like:

A tool used by compliance auditors, financial teams, data engineers.

It should not feel like:

A student project

A startup landing page

A marketing website

It is a functional evaluation dashboard.

🔷 FINAL DESIGN OUTPUT

Produce:

Upload State Frame

Loading State Frame

Dashboard State Frame

Tablet Version

Mobile Version

Component Library Page

Ensure clean alignment and visual consistency.