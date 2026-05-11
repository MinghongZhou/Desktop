# Plan: Become a Senior Machine Learning Engineer

**Date:** 2026-05-11
**Status:** active

## Goal

Build the skills, experience, and habits needed to operate at a senior MLE level:
strong ML fundamentals, production engineering, system design, and technical leadership.

---

## Phase 1 — Foundations (Months 1–3)

### Mathematics & Statistics
- [ ] Linear algebra: vectors, matrices, eigendecomposition, SVD
- [ ] Calculus: gradients, chain rule, Jacobians, Hessians
- [ ] Probability & statistics: distributions, Bayes' theorem, MLE/MAP
- [ ] Information theory: entropy, KL divergence, mutual information

### Classical ML
- [ ] Supervised learning: linear/logistic regression, SVMs, decision trees, ensembles
- [ ] Unsupervised learning: k-means, PCA, GMMs, autoencoders
- [ ] Model evaluation: cross-validation, bias-variance tradeoff, AUC-ROC, calibration
- [ ] Feature engineering: encoding, scaling, imputation, feature selection

### Resources
- [ ] Read: *Pattern Recognition and Machine Learning* (Bishop) — ch. 1–4
- [ ] Read: *Hands-On Machine Learning* (Géron) — full book
- [ ] Complete: fast.ai Practical Deep Learning Part 1

---

## Phase 2 — Deep Learning & Specialization (Months 3–6)

### Deep Learning Core
- [ ] Neural networks: backpropagation, activations, optimizers (Adam, AdaGrad)
- [ ] Regularization: dropout, batch norm, weight decay, data augmentation
- [ ] CNNs: architectures (ResNet, EfficientNet), transfer learning, object detection
- [ ] RNNs / LSTMs / GRUs: sequence modeling, attention mechanisms
- [ ] Transformers: self-attention, positional encoding, BERT, GPT, ViT

### Choose a Specialization Track (pick one or two)
- [ ] NLP: fine-tuning LLMs, RAG, embeddings, evaluation (BLEU, ROUGE, LLM-as-judge)
- [ ] Computer Vision: segmentation, detection, multi-modal models
- [ ] Recommendation Systems: collaborative filtering, two-tower models, ranking
- [ ] Time Series: forecasting, anomaly detection, temporal CNNs

### Resources
- [ ] Read: *Deep Learning* (Goodfellow et al.) — ch. 6–12
- [ ] Complete: fast.ai Part 2 (From Deep Learning Foundations to Stable Diffusion)
- [ ] Work through: Andrej Karpathy's *Neural Networks: Zero to Hero* series
- [ ] Paper: *Attention Is All You Need* (Vaswani et al., 2017)

---

## Phase 3 — ML Engineering & Production (Months 6–9)

### MLOps & Production Systems
- [ ] Data pipelines: Spark, Kafka, Airflow, dbt
- [ ] Experiment tracking: MLflow or Weights & Biases
- [ ] Model versioning and registries
- [ ] Serving: REST APIs (FastAPI), gRPC, batch vs. real-time inference
- [ ] Containers & orchestration: Docker, Kubernetes basics
- [ ] CI/CD for ML: automated retraining, model validation gates

### Distributed Training
- [ ] Data parallelism vs. model parallelism
- [ ] PyTorch DDP / FSDP
- [ ] Mixed precision training (FP16/BF16)
- [ ] Gradient checkpointing, memory optimization

### Monitoring & Reliability
- [ ] Data drift and concept drift detection
- [ ] Model performance dashboards (Prometheus, Grafana)
- [ ] Alerting, shadow mode, canary deployments
- [ ] A/B testing and online evaluation

### Resources
- [ ] Read: *Designing Machine Learning Systems* (Chip Huyen) — full book
- [ ] Read: *Machine Learning Engineering* (Andriy Burkov)
- [ ] Build: end-to-end project with training, serving, monitoring, and retraining

---

## Phase 4 — System Design & Leadership (Months 9–12)

### ML System Design
- [ ] Design recommendation systems at scale
- [ ] Design real-time fraud detection pipelines
- [ ] Design search and ranking systems
- [ ] Feature stores: Feast, Tecton — trade-offs and use cases
- [ ] Two-phase retrieval: recall vs. ranking layers

### Software Engineering Depth
- [ ] Data structures & algorithms (LeetCode medium — 100+ problems)
- [ ] System design fundamentals: CAP theorem, sharding, caching, load balancing
- [ ] Python performance: profiling, Cython, multiprocessing vs. threading
- [ ] Code quality: design patterns, testing (pytest), code review skills

### Technical Leadership
- [ ] Write design documents for new projects
- [ ] Present work internally and in blog posts / papers
- [ ] Mentor junior engineers on at least one project
- [ ] Drive a cross-functional project from scoping to deployment
- [ ] Participate in on-call and incident response for an ML service

### Resources
- [ ] Study: *ML System Design* interview guide (Educative / Stanford CS329S)
- [ ] Practice: mock ML system design interviews (2–3 per month)
- [ ] Read: engineering blogs (Meta AI, Google DeepMind, Uber, Netflix, Airbnb)

---

## Phase 5 — Portfolio & Career (Ongoing)

### Open Source & Visibility
- [ ] Contribute to a major ML library (PyTorch, HuggingFace, scikit-learn)
- [ ] Publish at least 2 technical blog posts on end-to-end projects
- [ ] Maintain a public GitHub with reproducible, well-documented projects

### Projects (build at least 3 end-to-end)
- [ ] Fine-tune and serve an LLM with RAG, evaluation, and monitoring
- [ ] Build a real-time recommendation or ranking system
- [ ] Train a model on distributed hardware and optimize inference latency

### Networking & Interviews
- [ ] Attend 2+ ML conferences or meetups per year (NeurIPS, ICML, local groups)
- [ ] Solve 150+ LeetCode problems (focus: medium, arrays, DP, graphs)
- [ ] Complete 5+ mock ML design interviews
- [ ] Apply to senior MLE roles with a strong portfolio narrative

---

## Key Milestones

| Milestone | Target Date |
|---|---|
| Complete Phase 1 fundamentals | Month 3 |
| Ship first end-to-end ML project | Month 5 |
| Complete specialization track | Month 6 |
| Ship production ML service with monitoring | Month 9 |
| First open source contribution merged | Month 10 |
| Published 2 blog posts | Month 11 |
| Ready for senior MLE interviews | Month 12 |

---

## Notes

- Prioritize building things over passive reading — aim for 60% hands-on, 40% study.
- Keep a weekly learning log in `plans/active/2026-05-11-senior-mle-weekly-log.md`.
- Revisit and update this plan monthly to reflect actual progress.
