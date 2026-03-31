# AI Risk Assessment Report
## NovaMind Customer Sentiment Analysis Model v3.2

**Document Reference**: AI-RISK-2025-003
**Author**: Dr. James Liu, AI Ethics Lead
**Date**: February 20, 2025
**Classification**: Confidential

---

## 1. Executive Summary

This AI Risk Assessment evaluates the NovaMind Customer Sentiment Analysis Model (v3.2), a natural language processing system deployed for real-time customer feedback classification across NovaMind's SaaS platform. The assessment is conducted in alignment with **ISO/IEC 42001:2023** (AI Management System) and the **EU AI Act** risk classification framework.

The model processes customer reviews, support tickets, and survey responses to classify sentiment as positive, negative, or neutral, and to extract key themes for product improvement. It is classified as a **limited-risk AI system** under the EU AI Act.

## 2. AI System Description

| Attribute | Details |
|-----------|---------|
| Model Name | NovaMind Sentiment v3.2 |
| Model Architecture | Fine-tuned RoBERTa-large |
| Training Data | 2.1M labeled customer interactions (2020–2024) |
| Languages Supported | English, Spanish, French, German |
| Deployment | Cloud API (AWS us-east-1, eu-west-1) |
| Inference Volume | ~500K predictions/day |
| Intended Use | Customer feedback classification |
| Not Intended For | Credit scoring, hiring decisions, law enforcement |

## 3. Risk Register

| Risk ID | Scenario | Likelihood | Impact | Risk Level | Mitigation |
|---------|----------|-----------|--------|------------|------------|
| R-001 | Demographic bias in sentiment scores | Medium | High | High | Bias audits quarterly, demographic parity constraints |
| R-002 | Training data poisoning via adversarial inputs | Low | Critical | Medium | Input validation, anomaly detection pipeline |
| R-003 | Model drift degrading accuracy over time | High | Medium | Medium | Weekly drift monitoring, automated retraining triggers |
| R-004 | Privacy leakage through memorized PII in outputs | Low | High | Medium | Differential privacy during training, PII scrubbing layer |
| R-005 | Misuse for automated decision-making without human review | Medium | High | High | API rate limits, mandatory human-in-the-loop for escalations |
| R-006 | Lack of explainability for negative classifications | Medium | Medium | Medium | SHAP explanations appended to all negative predictions |

## 4. Bias and Fairness Assessment

### 4.1 Methodology
Fairness evaluation conducted using the AI Fairness 360 toolkit across demographic groups (age, gender, language).

### 4.2 Results

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Demographic Parity Difference | 0.03 | ≤ 0.05 | ✅ Pass |
| Equalized Odds Difference | 0.04 | ≤ 0.05 | ✅ Pass |
| Disparate Impact Ratio | 0.92 | ≥ 0.80 | ✅ Pass |
| False Positive Rate Parity | 0.06 | ≤ 0.10 | ✅ Pass |

### 4.3 Identified Bias
The model exhibits a minor positive sentiment bias (+2.3%) for English-language inputs compared to Spanish inputs. Mitigation: Additional Spanish-language fine-tuning data collected (50K samples), scheduled for v3.3 release.

## 5. Transparency and Explainability

- **Model Cards**: Published internally and to enterprise clients
- **SHAP Explanations**: Top-5 contributing tokens displayed for each prediction
- **Data Sheets**: Training data provenance documented per Gebru et al. framework
- **Audit Trail**: All predictions logged with input hash, output, confidence score, and SHAP values

## 6. Human Oversight

- All predictions with confidence < 0.7 are routed to human reviewers
- Quarterly manual audit of 1,000 randomly sampled predictions
- Kill switch available to disable model inference within 2 minutes
- Escalation procedure defined for systematic misclassifications

## 7. Robustness Testing

| Test Type | Result |
|-----------|--------|
| Adversarial text injection | 97.2% resilience (TextFooler benchmark) |
| Out-of-distribution detection | 94.5% detection rate |
| Load testing (10x normal volume) | <200ms p99 latency maintained |
| Catastrophic forgetting (after retraining) | <0.5% accuracy degradation |

## 8. Governance and Accountability

- **AI Ethics Board**: Reviews high-risk AI deployments quarterly
- **Responsible AI Lead**: Dr. James Liu (reports to CTO)
- **Lifecycle Process**: Follows ISO 42001 AIMS lifecycle (Plan → Develop → Deploy → Monitor → Retire)
- **Incident Response**: AI-specific incident playbook with 4-hour SLA

---
*This assessment will be reviewed upon model update or within 12 months, whichever is earlier.*
