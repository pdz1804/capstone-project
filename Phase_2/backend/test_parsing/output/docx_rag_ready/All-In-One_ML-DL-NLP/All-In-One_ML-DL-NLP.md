# All-In-One_ML-DL-NLP


## 1. Machine Learning - Deep Learning

- Supervised learning: the learner (learning algorithm) are trained on labeled examples, i.e., input where the desired output is known.
- Unsupervised learning: the learner operates on unlabeled examples, i.e., input where the desired output is unknown. ﻿
Reinforcement learning: between supervised and unsupervised learning. It is told when an answer is wrong, but not how to correct it.
- Evolutionary learning: biological evolution can be seen as a learning process, to improve survival rates and chance of having offspring
﻿The most common type: supervised learning.
– Classification: to find the class of an instance given its selected features.
– Regression: to find a function whose curve passes as close as possible to all of the given data points.


### 1.1: Evaluation Metrics and Techniques


#### 1.1.1. Confusion matrix

- Each row corresponding to the true class.
- By definition, entry Ci,j in a confusion matrix is the number of observations actually in group i, but predicted to be in group j.
- Element trên đường chéo là True, tổng tất cả element đó là trace(C).
- False positive: dự đoán là positive trong khi actual là negative
- TP+FP = số dòng label positive trên tập PREDICTED
- TP+FN = support(P) = số dòng label positvive trên tập ACTUAL
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_1_c2e176b8.png|c2e176b8f8dee25039fbee908e31eb6b [END_IMAGE_PATH]


#### 1.1.2. Empirical methods

An empirical method is ﻿a quantitative method that analyzes numbers and/or statistics to study a research question on behaviors or phenomena. It derives knowledge from experience (rather than from theory or belief)
﻿Quantitative methods: Characterized by objective measurements
Qualitative methods: Emphasizes the understanding of human experience
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_2_273bfb93.png|273bfb937f82c77b38d8b1aa5d964719 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_3_68f77162.png|68f771628954cae18c8b01a145ed85a6 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_4_e0c6573a.png|e0c6573a2f5acf68801cc0db3cfadc6b [END_IMAGE_PATH]
- Precision: TP/TP+FP = Correct Predictions / Positive Predictions, focus this if false positive is costly (missing negative cases) i.e. detecting plagiarism, detects a student plagiarizing other work when they actually did not is unethical.
+ Precision answers: How many of the found instances are correct?
- Recall: TP/TP+FN = TP/support(P) = Correct Predictions / Positive Label, focus this if false negative is costly i.e. medical diagnosis, not detecting COVID when a patient actually has COVID is dangerous
Recall answers: How many of the correct instances have been found?
- Accuracy: trace(C) / sumdata, với sumdata là tổng số data, phù hợp với balanced dataset. F1-score khá là overkill, nếu xài thì xài macro avg f1 vì nó treat all classes equally
- F1: harmonic mean = 2PR / P+R
- macro avg: tổng chia N; weighted avg: tổng (w_i * value_i), với w_i = support(i) / sumdata
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_5_68d044b9.png|68d044b96c6bab8852c3955dd6b90856 [END_IMAGE_PATH]
Best metric còn tuỳ thuộc vào use case. VD: ensure customers with satisfaction issues (i.e., "Unsatisfied" customers) are properly identified => có thể xài recall nhưng phải là recall của Unsatisfied, tức Positive=Unsatisfied và negative = Satisfied


#### 1.3. Real-life case


##### 1.3.1. Dataset nhỏ

- Dễ gặp overfitting, accuracy của train cao hơn validation, scarcity làm tăng variance, mô hình cannot generalize well-> xài precision hoặc recall thôi chưa đủ.
Kĩ thuật chống small dataset
- Cross-validation: k-fold (﻿Randomly partitioned k equal sized sub-samples, k-1 train, 1 validate, lặp k lần và tính average result) hoặc stratified k-fold (tỉ lệ lớp dc bảo toàn trong mỗi fold nếu có thêm vđe class imbalance). Nếu dataset cực nhỏ thì k cũng nên nhỏ, tầm 3-5.
- Transfer learning: sử dụng pretrained model từ dữ liệu lớn sau đó fine-tune trên tập hiện tại
- data augmentation: tạo thêm data cho minor qua việc transform. thường dùng cho hình ảnh (xoay ảnh, affine transformation, scaling), âm thanh, chuỗi thời gian, số (thêm gaussian noise), văn bản (synonymize words, increase noise). dùng trong speech recognition và object recognition
- reduce model parameters (số neuron ẩn, số lớp ẩn, số tham số trong polynomial function...) => reduce complexity tránh overfitting
- ensemble methods, hiệu quả với data nhỏ khi kết hợp với CV


##### 1.3.2. Large samping bias

- aka large class imbalance -> accuracy is worst metric. Xài F1 tập trung cho minority class, xài weighted F1 thay vì macro-F1 nếu muốn overall performance. Lưu ý nếu tập trung vào minority class thì có thể xài macro avg.
Kĩ thuật chống class imbalance
PP chung:
class weighting (tăng weight cho minority trong loss function): w_i = sumdata / support(i)
data augmentation
Với Large data: undersampling (random undersampling)
Với Small data: oversampling (increase data for minority):
random oversampling: nhanh nhưng dễ overfit do trùng data
smote: interpolation between neighbor data: new = labelA + rand(0,1)*(labelB-labelA), giảm overfit so với random oversampling


##### 1.3.3. Macro-avg vs Weighted-avg

When to Use Macro-Average: Balanced datasets or when all classes are equally important; Small datasets with imbalance, to avoid bias toward the majority class; The minority class’s performance is critical (e.g., medical diagnostics).
When to Use Weighted-Average: Imbalanced datasets where the majority class reflects the real-world distribution or has greater impact; Large datasets where the overall performance across all samples is the priority.


##### 1.3.5. Bias-Variance tradeoff

Is the balance between two types of errors affecting a model's performance:
 Bias: Error due to overly simplistic assumptions in the model (underfitting). High bias means the model fails to capture the underlying patterns in the data.
 Variance: Error due to excessive sensitivity to small fluctuations or noise in the training data (overfitting). High variance means the model performs well on training data but poorly on unseen data.
 Low Bias, High Variance: Complex models (e.g., deep networks with many layers) fit training data well but may overfit, leading to poor generalization.
 High Bias, Low Variance: Simple models (e.g., linear regression) generalize better but may miss complex patterns, underfitting the data.
 Optimal Point: The goal is to find a balance where total error (Bias² + Variance + Irreducible Error) is minimized. This is achieved by: a) Increasing model complexity (e.g., more features, layers) to reduce bias, but applying regularization (e.g., dropout, L2) or more data to control variance; b) using techniques like cross-validation to tune hyperparameters and assess the tradeoff


##### 1.3.7. Handling missing values

1. Imputation with Mode (Most Frequent Value). Ignores the relationship with other features (e.g., Text Sentiment = Neutral, Image Quality = Good), and may introduce bias if the mode doesn’t reflect entry #6’s context.
2. Imputation Based on Class Similarity: Assign the "Product Visibility" value based on the most common value among entries with the same "Satisfaction" value (Satisfied) and similar feature values (e.g., Text Sentiment or Image Quality).
3. Introduce "missing" value. Noted that when constructing the decision tree (e.g., using ID3 with entropy), "Image Quality" splits will now consider four branches: Good, Fair, Poor, and Missing. But it has overfitting risk. With only one "Missing" entry, the tree might overfit by creating a specific branch for "Missing" that doesn’t generalize well to the test set.
4. Use inference-based tools to predict best possible value e.g. bayesian learning, decision tree induction, KNN
- Clustering techniques i.e. KNN: treat missing value imputation as a form of similarity-based prediction. Compute distance (e.g. euclidean) between the missing entry and all other entries using the non-missing features, then Choose the 'k' entries with the smallest distances (most similar). For a categorical feature, take the majority class among the k neighbors. For numerical just fill with average.


#### 1.4. Loss functions

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_6_1078f844.png|1078f844c78423ace78d5323481a2034 [END_IMAGE_PATH]
Squared units of the target -> less interpretable than RMSE => use RMSE for evaluation and reporting, easier to explain for stakeholders.
MSE is more sensitive (to large numbers and outliers); large errors are squared, amplifying their impact. But also because of squaring, it's useful for optimization (e.g., loss function in gradient descent) as it’s differentiable.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_7_37d5ece9.png|37d5ece98693da961d9bd2420eb3a435 [END_IMAGE_PATH]
Regression task: accuracy is not primary measure because it is nearly impossible to predict exact values of instances. We care about the error.


#### 1.5. Empirical Experiments


##### Development and evaluation

Train-val-test
Cross-validation: n-fold(i-th fold is used for validation, other folds are for training. The evaluation result is the average validation result over n folds), Stratified n-fold, Repeated CV (coincidental effects of random spltting is considered), Leave-one-out CV (avoid potential bias in splitting)
Stratified: ﻿The target variable distribution is kept stable across folds
﻿Pros and cons of cross-validation
• Often preferred when data is small, as more data is given for training
• Cross-validation avoids potential bias in a corpus split.
• Random splitting often makes the task easier, due to corpus bias.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_8_a49fe6b1.png|a49fe6b1f550393f55104cb15824dc68 [END_IMAGE_PATH]
Descriptive Statistics: ﻿Standard score: Indicates how many standard deviations a value is away from the mean of a distribution X; z-score: Indicates the precise location of a value Xi within a distibution X (Positive if above the mean, negative otherwise); t-score: Transforms a value rom a sample of size n into a standardized comparable form. Usually used for small samples (with less than 30 values)
Inferential Statistics: ﻿Procedures that help study hypotheses based on values. Used to make inferences about a distribution beyond a given sample


##### Hypothesis Testing

﻿Hypothesis test (aka statistical significance test): A statistical procedure that determines how likely it is that the results of an experiment are due to chance or sampling error
• Tests whether a null hypothesis H0 can be rejected (and hence, H can be accepted) at some chosen significance level
Significance level: The accepted risk (in terms of a probability) that H0 is wrongly rejected
Usually is set to 0.05 (default) or to 0.01. A choice of ↵ = 0.05 means that there is no more than 5% chance that a potential rejection of H0 is wrong.
In other words, with + 95% confidence a potential rejection is correct.
p-value: The likelihood (in terms of a probability) that results are due to chance
• If p <= alpha, H0 is rejected. The results are seen as statistically significant.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_9_d26e19bf.png|d26e19bf1b393e8dff9eb10dc332368d [END_IMAGE_PATH]


### C2: Decision tree


#### 2.1. Entropy

- measures impurity/disorder of a node, quantify uncertainty
- formula: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_10_8976394a.png|8976394af6f4499575559e5767a30667 [END_IMAGE_PATH](this is 1 sample)
This is for batch of N samples:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_11_3ce15e55.png|3ce15e555fc4873d1be3ec62dfa04a62 [END_IMAGE_PATH]
- used as a criterion for splitting in decision trees
- range: [0,1], 0 meaning 100% certainty and 1 means 50:50, maximum uncertainty


#### 2.2. Cross-entropy

A loss function measuring the difference between true label distribution and predicted distribution
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_12_a29da54d.png|a29da54df77bf6e3f713dc29f46842af [END_IMAGE_PATH]


#### 2.3. Information Gain

Measures the reduction in entropy after a split, guiding the choice of the best feature to split on. Core splitting criterion in ID3
Formula: Infogain = E(parent) - weightedAverageEntropy(children)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_13_fc76b2da.png|fc76b2da171aa78b2d476ae222489e1e [END_IMAGE_PATH]


#### 2.4. Gini index

- Core splitting criterion in CART (Classification and Regression Trees)[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_14_cc4c488b.png|cc4c488b84cdbe4f1592788bd652f0f6 [END_IMAGE_PATH]
Gini index is less sensitive to small changes near p=0 or p=1 compared to entropy, focusing on overall balance. It’s less aggressive in pursuing purity, which can help prevent overfitting.


#### 2.5. ID3

- A greedy, top-down approach of decision tree algorithm that uses information gain and entropy to build trees.
- Limitation: Handles only categorical feature and target variable and is prone to overfitting.
- Description:
+ Base: Compute E(root) = E(target feature). If E(root)=0 then subset is homogenious, we return a leaf node. Else we split.
+ Splitting: S is current node. For each feature A on the tree, compute IG(S,A) and choose best A based on highest IG. Then split the dataset into subsets based on the best feature.
+ Stopping condition: IG(S,A) = E(S) or pure nodes (E(S)=0, return as leaf) or no features left.
- Greediness: ID3 makes locally optimal choices without backtracking.


#### ﻿2.7. Problem with Decision Tree

Problem: attributes with a large number of values.
More Subset, more attribute values −→ Likely to be pure −→ Gain() biased towards choosing attributes with a large number of values.
This may cause several problems:
• Overfitting: selection of an attribute that is non-optimal for prediction.
• Fragmentation: data are fragmented into (too) many small sets. −→ Too deep and complex tree.
We only want a brief tree.
Solution: Intrinsic information and Gain Ratio Reduces its bias towards multi-valued attributes
Solution: Gini Index: Replace E(S) with Gini(S), I(S,A) with Gini(S,A)
Gini impurity is computationally efficient as compared to entropy. It is not ideal to use entropy when we have continuous feature values or having larger dataset as it will take more time. On the other hand, it is efficient to use Gini impurity as it takes less time to do the computation (Entropy have Log2 function, where Gini is just algebric)


#### 2.8. Pruning

- Is a Technique to reduce overfitting by removing branches that provide little predictive power.
Types: Pre-pruning (stopping tree growth early) and Post-pruning (trimming after growth).  Role: Improves generalization on unseen data.
- Types of Criteria for pre-pruning: max depth, min samples per split (min samples to break a node), min samples per leaf, min infogain (stop if gain <0.01), max features
- For post-pruning: reduced error pruning, min leaf size
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_15_e0cd6987.png|e0cd6987545519268942a1e53eae90fc [END_IMAGE_PATH]
Xây dựng Decision Tree: Tính initial entropy -> Tính info gain -> Chọn root node (info gain cao nhất) giả sử là A -> Tạo branch cho A (các label của A) -> Split


#### 2.9. Random forest

- is an ensemble method that builds multiple decision trees and combines their predictions.
- It reduces overfitting by using randomness:
+ Bagging (Bootstrap Aggregating): Each tree is trained on a random subset of the training data (sampling with replacement)
+ Feature Randomness: Each tree only considers a random subset of features at each split, making trees diverse.
The final prediction is made by majority voting (classification) or averaging (regression).
=> Lower variance due to averaging, Lower overfitting risk (generalizes better), interpretability is lower (harder to interpret many trees and more metrics to evaluate)


#### 2.10. Regression tree

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_16_8b6f0298.png|8b6f02987a7db080ffa9b536b2b7e716 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_17_ef8f9a79.png|ef8f9a799e2051804134764152c873a6 [END_IMAGE_PATH]
The threshold with lowest total SSE is t=3.5 (total SSE = 2).
Answer: In an exam you’d show exactly this table of candidate midpoints, compute each side’s mean and squared error, and conclude x≤3.5 vs x>3.5 is the optimal first split.


### C3: Perceptron and Deep Neural network


#### 3.1. Perceptron and XOR problem

- cannot solve non-linearly separable problems. Eg. XOR (if we stack multiple layer we can solve it -> MLP). In addition, training time grows exponentially with the size of the input.
Use stacked perceptrons for the XOR problem:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_18_9ba3ff7d.png|9ba3ff7d596ba3435bcb46750d85256c [END_IMAGE_PATH]


#### 3.2. Activation function

- Must be differentiable at all points (smooth) for easy derivation


##### 3.2.1. Examples and Comparison

Example: tanh, sigmoid, relu, gelu, elu[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_19_c4c1f3d6.png|c4c1f3d66c3dd86cd504110d159033f9 [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_20_7496e5b2.png|7496e5b2df897eec5d670cfb04545b03 [END_IMAGE_PATH]
Derivative:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_21_f893129c.png|f893129c3d18448b30450276803bcc5c [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_22_967fbf0d.png|967fbf0df2a21b9ada962b7f2976dc8b [END_IMAGE_PATH]
ReLU: =1 if x>0; =0 if x <0, undefined if x=0
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_23_1f025a7b.png|1f025a7b6ac50a6dc80c8a567839c597 [END_IMAGE_PATH](both tanh,sigmoid are smooth and bounded)
+ Tanh: can work with small datasets, as its output range [−1,1] is zero-centered, helping gradients flow better than sigmoid. However, it’s prone to vanishing gradients (gradients approach 0 for large ∣x∣), which might slow convergence with very small datasets.
+ Sigmoid also suffers from vanishing gradients and is not zero-centered.
+ ReLU =max(0,x) is simple and effective, with no vanishing gradient for x>0. However, with small datasets, it can suffer from the "dying ReLU" problem
﻿+ Sigmoid function saturates at 1 for large positive inputs, and at 0 for large negative inputs.
+ tanh function saturates at -1 and +1.
+ In the saturated regimes, the gradient of the output wrt the input will be close to zero. Thus, any gradient signal from higher layers will not be able to propagate back to earlier layers.
+ ELU (Exponential Linear Unit)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_24_fa19bccc.png|fa19bccc0b1420dfb9bf0318fa7ce7ce [END_IMAGE_PATH]
Range of ELU: [-α,inf]
ELU mitigates the dying ReLU problem by outputting negative values for x<0, improving gradient flow. It can work well with small datasets if α is tuned.
For hidden layers: avoid vanishing gradients => choose ReLU, ELU. because of their range, they are not suitable for the output layer in binary classification and require a sigmoid function; for regression still needs a linear output layer.
Tanh/sigmoid is very good as output layer. Sigmoid is best for binary classification, tanh is also okay since we can map ([0,1] is 1, [-1,0) is 0)
For shallow MLP (1-3 hidden layers): ELU has best performance; for Deep MLP use GELU (Gaussian Error Linear Unit)
For Deep neural network: tanh/sigmoid is rarely used due to vanishing gradients and slow convergence. ReLU has fast convergence but has dying ReLU. GELU is best, used in transformers like BERT.
For Single perceptron: just use tanh/sigmoid. ReLU/GELU/ELU have unbounded or semi-bounded ranges.


##### 3.2.2. Vanishing gradients

Occurs when gradients (derivatives of the loss with respect to weights) become very small during backpropagation, leads to tiny weight updates, slowing or stalling learning (slow convergence).
For sigmoid, the derivative σ′(z)=σ(z)(1−σ(z)) reaches a maximum of 0.25 at z=0 and approaches 0 for large positive or negative z z z, slowing weight updates. Tanh has a similar issue, with gradients approaching 0 for large |z∣. This is especially problematic in deep networks where gradients are multiplied across layers, less occur in small dataset.
Solution:
  Input Normalization: Scale inputs to keep z in a range where gradients are large (e.g., z≈0 for sigmoid, maximizing σ′(z)≈0.25). For your dataset, normalize features (e.g., 2, 1, 0 → 1, 0.5, 0) to prevent saturation.
  Small Weight Initialization: Initialize weights to small values (e.g., w_i∼Uniform(−0.01,0.01)) to keep initial z small, ensuring sigmoid outputs are near 0.5.
  Higher Learning Rate: Increase the learning rate η to amplify small gradients, e.g., start with η=0.5, then reduce to 0.1 after 50 epochs, balancing speed and stability.
  Gradient Clipping: Clip gradients to a minimum (e.g., if ∣gradient∣<0.01, set to 0.01) to ensure updates aren’t negligible, especially with sigmoid’s small gradients (max 0.25).
  Perceptron Rule: Use the perceptron learning rule of gradient descent, bypassing the activation function’s gradient, which is ideal for your single perceptron with sigmoid.


##### 3.2.3. Exploding gradients

- Gradients grow too large, often due to poor weight initialization or deep networks with many layers, the gradients are multiplied. This causes weight updates to overshoot, leading to unstable training and diverging loss. It’s less common in single perceptrons but can happen if weights are initialized too large, causing z to grow exponentially. For example, in deep recurrent neural networks, long sequences can amplify gradients, but your shallow model is less prone.
Solution: Gradient Clipping:
Cap gradients at a maximum (e.g., if ∣gradient∣>1.0, set to 1.0) to prevent overshooting, applicable if weights grow large. For your perceptron, this is less critical but useful if initial weights are large.
  Weight Regularization: Add L2 regularization to the loss (λ∑w_i^2, λ=0.01) to penalize large weights, keeping z small and preventing explosions. For your model, this ensures stability during training.
  Proper Weight Initialization


##### 3.2.4. Gradient Based Learning

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_25_8ac4193f.png|8ac4193fd97edd67e6fad42326de9cf7 [END_IMAGE_PATH]
﻿2. Sigmoid Units for Bernoulli Output Distributions
• Task: predicting the value of a binary variable y[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_26_84462694.png|84462694ba29c2413f7abb8bf2047b7f [END_IMAGE_PATH]
﻿Maximum likelihood is almost always the preferred approach to training sigmoid output
units.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_27_afb8b06d.png|afb8b06db638f0a0f15c68f5852c3f6c [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_28_d2e31313.png|d2e3131388acaf1cded3bb118e8370e0 [END_IMAGE_PATH]
For single-label classification: Use Softmax as activation function and Cross-Entropy Loss
For multi-label classification: Use Sigmoid and Binary Cross-Entropy loss functions, then take their sum
For binary classigication: Softmax (model has 2 outputs) or Sigmoid (1 output) + BCE


#### 3.3. Linear models

• Logistic regression, linear regression[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_29_c24a1422.png|c24a1422e3e013ac4739862b5774987d [END_IMAGE_PATH]
• Can be fit efficiently and reliably
• Can obtain closed form solution or with convex optimization
• Limitation: capacity is limited to linear functions. Make strong assumption that input-output mapping is linear.
• Can not understand the interaction between any two input variables


#### 3.4. Designing DNN/MLP

- DNN is a DAG
- Encoding: categorical encoding or one-hot encoding. If small dataset, avoid one-hot because it generates N-1 binary features for a feature with N label. This could leads to overfitting, the model does not have enough examples to learn the weights w.
- Calculating: z = sum(w_i*value(i)); z >= 0 => class 1, else 0.
- Pipeline:
- Value of weight and bias matrices
- Binary CrossEntropy as a loss function
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_30_19b739a1.png|19b739a17808b4fde1e59df8242bfa61 [END_IMAGE_PATH]


#### Stochastic Gradient Descent

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_31_3c104d00.png|3c104d004c5d36fb0731ff170152c7e0 [END_IMAGE_PATH]
﻿SGD gradient estimator introduces a source of noise: the random sampling of m training
examples => Does not vanish!
• Crucial parameter: learning rate alpha => Should be adapted over time
﻿


#### Batch and Minibatch Algorithms

• Objective function usually decomposes as a sum over the training examples
• Optimization: update the parameters based on an expected value of the cost function
estimated using only a subset of the full cost function
• Batch or deterministic gradient methods: process all of the training examples
simultaneously in a large batch
• Stochastic (or online methods): use only a single example at a time
• Most algorithms used for DL fall somewhere in between, using more than one but less
than all of the training examples
﻿- Minibatch sizes:
• Larger batches: provide a more accurate estimate of the gradient, but with less than
linear returns.
• Multicore architectures are usually underutilized by extremely small batches
• Using some absolute minimum batch size: no reduction in the time to process a minibatch
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_32_9de953a3.png|9de953a33b95ca0194f8e790bd977617 [END_IMAGE_PATH]


#### 3.5. Regularization

﻿là strategies are explicitly designed to reduce the test error, possibly at the expense of increased training error.
﻿Most regularization strategies are based on regularizing estimators
• Regularization of an estimator works by trading increased bias for reduced variance
• An effective regularizer: makes a profitable trade, reducing variance significantly while not overly increasing the bias[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_33_e39aec91.png|e39aec916ea36bacbdd7a4a9c3d43fe1 [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_34_dca917c1.png|dca917c154e1300494cc80827fbfecfc [END_IMAGE_PATH]
﻿The regularization contribution to the gradient no longer scale linearly with each w_i
• L1 regularization results in a solution that is more spare, comparing to L2: some
parameters have an optimal value of zero.
• Sparsity property of L1 regularization has been used extensively as a feature selection
mechanism
1 kỹ thuật khác là Early stopping: terminate when validation set performs better


#### 3.6. Dropout

﻿- provides a computationally inexpensive but powerful method of regularizing a
broad family of models
- ﻿Good for five to ten neural networks
• Dropout trains the ensemble consisting of all sub-networks that can be formed by
removing non-output units from an underlying base network
﻿Very computationally cheap
• Using dropout during training requires only O(n) computation per example per update, to
generate n random binary numbers and multiply them by the state
• Dropout does not significantly limit the type of model or training procedure that can be
used
﻿For very large datasets
• Regularization confers little reduction in generalization error
• The computational cost may outweigh the benefit of regularization
• Very few data samples
• Dropout is less effective
• When additional unlabeled data is available, unsupervised feature learning can gain an
advantage over dropout


##### Bagging vs dropout

﻿Bagging
• The models are independent
• Each model is trained to convergence on its respective training set
Dropout
• Models share parameters
• most models are not explicitly trained at all
• It is infeasible to sample all possible subnetworks within the lifetime of the universe
• The remaining sub-networks to arrive at good settings of the parameters
• Dropout can represent an exponential number of models with a tractable amount of
memory


#### 3.7. Challenge of Neural network optimization

- ﻿SGD can get "stuck": even very small steps increase the cost function
﻿- Saddle point: point with zero gradient
• A local minimum along one cross-section of the cost function and a local maximum along
another cross-section
• In low-dimensional spaces: local minima are common
• In higher dimensional spaces: local minima are rare and saddle points are more common


#### 3.8. Exercise Examples

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_37_b1780b67.png|b1780b67eff4814789e7cb8dfe06d0c5 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_38_caed7e9f.png|caed7e9ff51cf69a9838aff134c026b6 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_39_5761087c.png|5761087c7ce6a964580acf9d8e593266 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_40_6e964e2d.png|6e964e2d00b5fb9fc6cae0136e291c0f [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_35_488251cf.png|488251cfaa70045cda844a1d6180214e [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_36_6df432ab.png|6df432ab55d9750781b6130c0d10aced [END_IMAGE_PATH] (BCE loss)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_41_db32190a.png|db32190a07af7ee987c7376e3f982372 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_42_5f81a8c4.png|5f81a8c48cb7a46be55b02799bbf15ff [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_43_f0b359db.png|f0b359db82549eca6a851650ab89a378 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_44_c2590fa5.png|c2590fa59604708c362a7c9dbc1e6a4d [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_45_8695361a.png|8695361a6c2745c15028d7e463167aef [END_IMAGE_PATH]
For MSE loss (Regression) with Loss = 1/2(a-y)^2:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_46_b5139c24.png|b5139c241fe9954d38aadb7362fa3804 [END_IMAGE_PATH] Delta: Gradient of L wrt. z
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_47_8aa3a217.png|8aa3a2171a9e073c34c1f56376e7240c [END_IMAGE_PATH]
w = [0.5, -0.2, 0.3]  (initial weights); lr = 0.1 (learning rate)

[START_TABLE_CONTENT] | Method | Speed | Noise | Update Frequency |
| --- | --- | --- | --- |
| SGD | Fast per-step | Noisy | High |
| Mini-batch | Slower step | Smoother | Lower | [END_TABLE_CONTENT]

SGD-style (left) vs Mini-batch (right)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_48_59633b32.png|59633b32f569c22d81523c247507db76 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_49_d49bcb74.png|d49bcb741815cb22b81068a9be4aa988 [END_IMAGE_PATH]


### C4: Linear regression (Supervise)

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_50_66394585.png|66394585b2ede8a8deb5823e3211cf7f [END_IMAGE_PATH]
Linear Regression: The weight must be linear, not data
Suppose you're predicting final grades based on study hours => True regression function: The real average grade of all students in the universe who study for 5 hours. Empirical regression: The average grade of students in your training dataset who studied 5 hours. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_51_8412b5b2.png|8412b5b29adb5c66ff82d5427bd39b76 [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_52_b61761bd.png|b61761bdace16413ce2dd0b60a9a2d39 [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_53_d5cad5b8.png|d5cad5b8434ab42906456eee81eaeede [END_IMAGE_PATH]
Regularization (factor) increase too high -> underfitting -> training loss is consistently high, the decrease over time is not steep enough
Regularization decrease -> overfitting -> decrease training loss and increase validation loss
Step size too small -> training loss decrease gradually but slower convergence (as numepoch increase). Step size too large -> training loss decrease significantly but validation loss may not. If overshoot the optima, training loss can increase (as numepoch increase)


### C5: Logistic Regression

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_54_4f145c21.png|4f145c2116e06e8c739ed1734d186a53 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_55_df558ece.png|df558ececeb536dad65d681733ab880b [END_IMAGE_PATH]
Negative likelihood loss for logistic regression is guaranteed to be convex.
﻿The problem of minimizing L(w) is an unconstrained optimization problem, and iterative methods can be used.
- Based on the first derivative: Gradient Descent
- Based on the second derivative: Newton-Raphson
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_56_65192799.png|65192799ffb5de71f5116b7d977c102b [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_57_aa562b87.png|aa562b87ba72f45c4478af7649f72e61 [END_IMAGE_PATH]
The intercept in a logistic regression model represents the log-odds of the outcome when all predictor variables are equal to zero. It serves as the baseline log-odds for the reference case in the absence of any predictor effects.
For example, if the intercept is -2, the baseline odds are e^(-2) ≈ 0.135[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_58_32a432ff.png|32a432fff7c99765e2df0e410a006abe [END_IMAGE_PATH]
 Odds = e^(Log-odds) = e^(β₀ + β₁X₁ + β₂X₂ + ... + βₙXₙ)
 Probability = 1 / (1 + e^(-Log-odds)) or Probability = 1 / (1 + e^-(β₀ + β₁X₁ + β₂X₂ + ... + βₙXₙ)) = Odds / 1+Odds
Suppose a logistic regression model predicts the likelihood of a customer buying a product, with a predictor "age" having a coefficient of 0.1:
 A one-year increase in age increases the log-odds of purchasing by 0.1.
 The odds ratio is e^0.1 ≈ 1.105, meaning each additional year of age increases the odds of purchasing by about 10.5%.
 The actual change in probability depends on the baseline probability and other predictors in the model.
For continuous predictors, the coefficient reflects the effect of a one-unit increase.
For categorical predictors, the coefficient compares the log-odds of one category (e.g. is_bought=Yes) to a reference category. (e.g. is_bought=No)
Standardized coefficients can be used to compare the relative importance of predictors.
The intercept in a logistic regression model represents the log-odds of the outcome when all predictor variables are equal to zero. It serves as the baseline log-odds for the reference case in the absence of any predictor effects.
If predictors are continuous (e.g., age, income), zero may not be meaningful unless the variables are centered (e.g., age = 0 might not make sense).
If predictors are categorical, the intercept represents the log-odds for the reference category (e.g., the baseline group when all dummy variables are zero).
If predictors are centered or standardized, the intercept reflects the log-odds at the mean of the predictors.
The model estimates coefficients (β) by maximizing the log-likelihood function, which measures how well the model explains the observed data.by maximizing the log-likelihood function, which measures how well the model explains the observed data. This is typically done using iterative methods like gradient descent.
Calculate Mean and Variance
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_59_b2a9ac2f.png|b2a9ac2f36f86cc17caf4c1c283c9c3c [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_60_77a5a133.png|77a5a13319ed9c3d31eaf2e1ea7fed9b [END_IMAGE_PATH]


### C6: Gradient Descent

﻿Convex function: if a line segment between any two points lies entirely “above” the graph
Simple algorithms like gradient descent have strong guarantees. But it does not work well for all convex functions
Saddle point: function goes up wrt x, goes down wrt y. ﻿most critical points in neural net loss landscapes are saddle points. ﻿The gradient around it is very small => takes a long time to get out of saddle points
=> ﻿the steepest direction is not alway the best. We dont always move towards the optimum
﻿Critical points: any point with gradient = 0 (can be maxima, minima, saddle)
﻿Local optima problem: becomes less of an issue as the number of parameters increases: For big networks, local optima exist, but tend to be not much worse than global optima => local optima is acceptable
Why we cannot jsut choose tiny learning rate to prevent oscillation and overshooting optima =>> Plateau warning! Needs ﻿learning rates to be large enough not to get stuck in a plateau
=> Momentum can help solve this
Newton's method: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_61_6e39c5f7.png|6e39c5f7bfdc55ef5a73d2f3917a2a3e [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_62_ef6b2980.png|ef6b2980daebb50c79c87ea483b4800a [END_IMAGE_PATH]
Issue: tractable acceleration -> runtime O(n^3) if naive (since O(n^2) to form Hessian matrix), compare to O(n) of gradient descent
=> ﻿prefer methods that don’t require second derivatives, but somehow “accelerate” GD instead
=> MOMENTUM (lấy đà): averaging together successive gradients (Accumulate gradients overtime)
Intution: ﻿ if successive gradient steps point in different directions, we should cancel off the directions that disagree. If successive gradient steps point in similar directions, we should go faster in that direction
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_63_cb6acc79.png|cb6acc7925a72cf0dc74eb1bce99830b [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_64_86b27c58.png|86b27c5866c19583b6f123f3fd8f6ce8 [END_IMAGE_PATH]
Gradient Scale: normalize the magnitude of gradient along each dimension to avoid exploding/vanishing magnitude which makes model harder to learn
=> RMSProp: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_65_db23f5eb.png|db23f5eb3329b27ee9c45e8946295a29 [END_IMAGE_PATH]
AdaGrad:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_66_73c3acf7.png|73c3acf789008d67eb0cbe222a605ad0 [END_IMAGE_PATH]
AdaGrad has some appealing guarantees for convex problems: Learning rate effectively “decreases” over time, which is good for convex problems. But this only works if we find the optimum quickly before the rate decays too much. also works best with sparse data (NLP task)
RMSProp tends to be much better for deep learning (and most non­convex problems)
Adam = Momentum + RMSProp[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_67_49716a08.png|49716a0853364dbe77ce3aefa95292ba [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_68_cef21bbc.png|cef21bbcff164669c1c0fc4051f76c27 [END_IMAGE_PATH]
SGD with minibatch: sum is over elements of B instead of S.
In practice: ﻿sampling randomly is slow due to random memory access => instead, shuffle the dataset (like a deck of cards…) once, in advance then just construct batches out of consecutive groups of B datapoints.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_69_56fed70c.png|56fed70c90db3acd19886d74169f5627 [END_IMAGE_PATH]
Tuning SGD on validation loss:
Batch size B: ﻿larger batches = less noisy gradients, usually “safer” but more expensive
LR alpha: ﻿best to use the biggest rate that still works, decay over time
Momentum \mu: 0.99 is good
Adam param \beta1, \beta2: keep default
﻿Learning rate decay schedules usually needed for best performance with SGD (+momentum). ﻿Often not needed with ADAM
Opinions differ, some people think SGD + momentum is better than ADAM if you want the very best performance (but ADAM is easier to tune)


### C7: Genetic algorithm

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_70_a8f570ea.png|a8f570ea4625585de04a1e3159c7d658 [END_IMAGE_PATH]
correct(h): number of correctly classified examples
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_71_7220c04c.png|7220c04c17a07e7195651cbeaf1d7210 [END_IMAGE_PATH]﻿
Parent s1, s2; Mask m
=> offstring 1: (s1 ^ m) v (s2 ^ !m); offstring 2: (s1 ^ !m) v (s2 ^ m)
Lưu ý select ở đây là with replacement.
Fitness proportionate selection can lead to crowding.
Tournament selection: In each tournament, two chromosomes are randomly chosen from the population, and the one with the higher fitness (recall for "Unsatisfied") is selected for the next generation.
Rank selection: sort hypotheses by fitness. The chance to get selected is proportional to rank.
VD bài TS-PV-IQ-Satisfaction
Chromosome representation:
- Attributes: Each attribute’s possible values are represented by a substring of bits. A 1 in a position means that value is allowed. A 0 means that value is not allowed.
- For an attribute like Text Sentiment (Positive, Neutral, Negative): Use a 3-bit substring: 100 means "Text Sentiment = Positive", 110 means "Text Sentiment = Positive or Neutral", 111 means "any value" (no constraint). 000 is invalid.
- For target variable (Satisfaction), we only use 1 bit (0 for Unsatisfied, 1 for unsatisfied). This is because the target variable cannot have more than one state at a time.
=> A chromosome will have 10 bits. Example: TS=Good,PV=High,....
Fitness function: vd mún ensure tất cả unsatisfied result đều đúng thì ta chọn fitness là Recall(Unsatisfied)
Selection operator: Tournament selection with a size of 2
Crossover operator: Uniform crossover hoặc variable-length string crossover
Must make sure no invalid strings e.g. containing '000' for a feature. If use variable-length string crossover, must preserve the number of bits divisible by 10 for semantic purpose.
Mutation operator: Use bit-flip mutation with a mutation rate of 0.1. For each bit in a chromosome, there is a 10% chance it will flip (0 → 1 or 1 → 0). Mutation rate of 0.1 ensures genetic diversity by occasionally introducing random changes, preventing the GA from getting stuck in local optima
Stopping Criteria: Stop the GA after 20 generations,  or if there is no improvement in the best fitness for 5 consecutive generations, or fitness function > 0.9
Population size: 10 random hypotheses at the start
Ví dụ thực tế:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_72_cf8adaa4.png|cf8adaa4ffa8707590fb2e48a5f8a97f [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_73_e75f8200.png|e75f8200e04283324036ba1f45f5aa88 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_74_a56e74a0.png|a56e74a0b34694502f3b8f02c4fd4cc7 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_75_d24ece3c.png|d24ece3c19da021593d1324f82054912 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_76_c4d543a9.png|c4d543a9e2fde59f05010e34961e48a8 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_77_7b5683c1.png|7b5683c1420811c6b0b7ea064b99ef65 [END_IMAGE_PATH]


### C8: Bayesian network & Naive bayes

Dạng bài Identify a case where the assumption of independence of Naive bayes might be violated. Calculate the joint probability P(TS,PV|Satisfaction) for 1 example in the training set, both with and without independence assumption to demonstrate the difference:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_78_73f903f2.png|73f903f2b6faf0329cf639da71d02de6 [END_IMAGE_PATH]
Let’s choose ID 1: TS=Positive, PV=High, Satisfaction=Satisfied....
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_79_b6ac0097.png|b6ac0097fec86f7c7817761b56ab3823 [END_IMAGE_PATH]


#### 5.1. Bayes optimal classifier

- Aims to achieve the lowest possible error rate for classifying data. It works by using Bayes' theorem to calculate the probability of each class given the input features and then picks the class with the highest probability. This means it relies on knowing the true probability distributions, which in practice, we usually don’t have, so we estimate them from data. It is based on Bayes' theorem, which computes the posterior probability if a class given the features: P(c∣x)=P(x∣c)P(c)/P(x)
where:
 c is the class (e.g., Satisfied or Unsatisfied),
 x is the feature vector (e.g., Text Sentiment, Product Visibility, Image Quality),
 P(c∣x) is the posterior probability,
 P(x∣c) is the likelihood,
 P(c) is the prior probability of the class,
 P(x) is the evidence, a normalizing constant.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_80_5e6f3128.png|5e6f312853d2c0d9e72a7ff7ed490b33 [END_IMAGE_PATH]
It selects the class with the highest posterior probability, minimizing the expected classification error.
For example, in customer satisfaction problem, it would calculate the probability of "Satisfied" or "Unsatisfied" given features like Text Sentiment, Product Visibility, and Image Quality, and choose the most likely class. This approach is ideal but hard to implement perfectly because it needs exact probabilities, which are often unknown.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_81_d38c8808.png|d38c88080a91b60be4ab0b4b3a37c916 [END_IMAGE_PATH]


#### 5.2. The Naive Bayes classifier

- is a simpler version of the Bayes optimal classifier. It makes a big assumption: all features are independent of each other given the class. This assumption simplifies the likelihood calculation:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_82_bd0a3338.png|bd0a3338024cc3734782bfeb9e79d4d6 [END_IMAGE_PATH]
Since P(x) is constant for all classes, we can simplify to:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_83_dd6d43c1.png|dd6d43c17d871ef189d5b386f41068fd [END_IMAGE_PATH]
This assumption reduces the number of parameters to estimate, as we only need P(x_i∣c) for each feature x_i​ and class c, rather than the joint P(x∣c).
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_84_8d91b507.png|8d91b5070402371e701e9dd219e18b01 [END_IMAGE_PATH]
﻿Naive Bayes is a generative model:
• It models a joint distribution: p(C; A)
• It can generate any distribution on C and A
This means, for instance, that Text Sentiment and Product Visibility don’t affect each other if we already know the Satisfaction level. This assumption lets us break down complex probability calculations into easier parts, multiplying individual probabilities instead of dealing with joint ones.
However, this assumption can be wrong. In your dataset, we saw Text Sentiment and Product Visibility might be related for "Satisfied" cases, like Positive sentiment often pairing with High visibility. When this happens, Naive Bayes might not be as accurate as the Bayes optimal classifier, which considers all dependencies. Still, Naive Bayes often works surprisingly well, because it’s simpler and reduces the risk of overfitting by estimating fewer parameters.
Laplace smoothing
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_85_468e22e6.png|468e22e618849dc0de0a739c8c076827 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_86_1ec61bb4.png|1ec61bb4929187e37c6e3adf21cd89ad [END_IMAGE_PATH]
Naive bayes: ﻿Posterior = Likelihood * Prior / Evidence (PLPE)
﻿Naïve Bayes Assumption: The attributes that describe the data are conditionally independent given the classification hypothesis => Issue: ﻿The film was beautiful, stunning cinematography and gorgeous sets, but boring.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_88_0f083a91.png|0f083a910d6c21f6537fca33675e1958 [END_IMAGE_PATH]
Maximum Likelihood Estimation[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_87_0025d238.png|0025d2385a223b4445de98c80aa01274 [END_IMAGE_PATH]
Log-likelihood:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_89_b60fe9ef.png|b60fe9ef40d091b941ac2b4264199cea [END_IMAGE_PATH]
Objective of NB: ﻿Estimate the posterior probability P(document|class) and the prior probability P(class)
﻿Likelihood: Assume the bag of words model: A document is a sequence of words (w1, . . . , wn); The order of words is not important; Each word is conditionally independent given the class of the document
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_91_ce1d1827.png|ce1d18272379e0d3bb1c23ae30e63dc3 [END_IMAGE_PATH]
Laplace smoothing for NB: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_90_88eadc13.png|88eadc130dc2b0fd2135b43db9ce83fb [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_15_e0cd6987.png|e0cd6987545519268942a1e53eae90fc [END_IMAGE_PATH]
Xây dựng mạng Naive Bayes:
1. Compute prior probability P(Attractive=Yes), P(Attractive=No)
2. Compute Conditional probability (Likelihoods): P(Feature|Class) e.g. P(height=small | attrative=yes), P(height=small | attractive=no)... make sure to use laplace smoothing.
3. Xây dựng mạng với công thức sau:
P(Class∣Features)∝P(Class)×P(Feature1​∣Class)×P(Feature2​∣Class)×P(Feature3​∣Class) x ...


### Support Vector Machine

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_92_670c01be.png|670c01bed99ad464dcd8202c8735d01b [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_93_02ff1543.png|02ff154300281b0c4fdc1524dd5ba6f6 [END_IMAGE_PATH]
Label‐(Ordinal) Encoding: Mobile→2, Desktop→1, Tablet→0
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_94_d2d6b109.png|d2d6b109f3ea7983aad626a6f0dd97f0 [END_IMAGE_PATH]Frequency Encoding
 Count occurrences in your 10 rows: Mobile = 4, Desktop = 4, Tablet = 2
 Divide by n (here n=10): Dev_freq: Mobile→0.4, Desktop→0.4, Tablet→0.2
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_96_34202c9d.png|34202c9d499fb7b4449680e694df2757 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_97_ce56ea1e.png|ce56ea1e229bbaef157839a7e17db57b [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_98_a3ccb184.png|a3ccb18455f33b28a7868a2208f8b1f2 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_95_015beff9.png|015beff94a668829cb5fc4d877d2891e [END_IMAGE_PATH](d):ax+by+c=0; M(x0,y0)


### Random Forest

Two key variance-reduction mechanisms in Random Forests
1. Bootstrap aggregation (“bagging”)
o Each tree is trained on a different bootstrap sample of the data (sampling with replacement).
o This injects diversity: some cases appear multiple times in one tree’s training set, none in another’s.
o Averaging the predictions across these differently trained trees smooths out the high-variance mistakes of any single tree.
2. Random feature subset at each split
o At each node of a tree, only a random subset of the full feature set is considered for splitting (rather than all features).
o This further decorrelates the trees—if one very strong predictor dominates early splits in every tree, all trees would look alike.
o By forcing each tree to “consider different questions,” the averages of many weakly correlated trees have much lower variance than any one tree.
Together, these two strategies let a Random Forest match (or exceed) the accuracy of a single deep tree while dramatically reducing its tendency to overfit.
Effect: Lower variance due to averaging, Lower overfitting risk (generalizes better), interpretability is lower (harder to interpret many trees and more metrics to evaluate)
Adjusting the decision threshold to catch more buyers
 To reduce false negatives (i.e. missing buyers), lower the threshold below 0.5—for example, classify “Yes” if ≥ 40% vote Yes.
 Effect: you’ll catch more actual buyers (higher recall) but also flag more non-buyers as buyers (higher false-positive rate).
 Downside: wasted marketing effort on more non-buyers, potentially higher costs or customer annoyance.


### Gradient Boosting

Gradient Boosting is an ensemble learning technique where models (typically decision trees) are added sequentially to correct the errors made by the existing model ensemble. Instead of fitting models to the original labels directly, each new model is trained to predict the residuals (errors) of the previous models. This allows the model to gradually improve over iterations.


#### Process

Step 0: Determine initial F0(x)
- For numerical: take average and apply to all rows
- For categorical: take p^ = average (if target-label is hard) or log-odds: log(p^ / 1-p^), if target label is soft.
Loop0:
Step 1: Compute Residuals (or pseudo-residuals)
Residuals represent how far off the model’s current predictions are from the true labels. This tells us how much error each prediction still has, which we want to correct.
For Continuous features, we use MSE = 1/2 sum((observe-target)^2). Therefore pseudoresidual r_i = y_i - F(x_i). This is also called true residual (literally the difference between the observed and target)
For Categorical features, we use log-loss. Therefore:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_99_040e3e3b.png|040e3e3b96400a2128a8e29af43a14d9 [END_IMAGE_PATH]
The sigmoid is used to model any number to {0,1} range
Because of this, it is not True residual.
Tổng quát: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_100_062179eb.png|062179eba5c0e191c6a9df2013225951 [END_IMAGE_PATH]
Step 2: Train a Weak Learner ℎ1(x)
We now train a small decision tree on these residuals, not on the original labels. This tree tries to predict where the current model is wrong and by how much.
Step 3: Update the Model
We add the tree’s predictions to the current model’s predictions, scaled by a learning rate/shrinkage.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_101_31caa3e6.png|31caa3e68f6bfbdc3602ab488a864293 [END_IMAGE_PATH]
IF there is no learning rate, We will heavily overfit to the training data (since F1(x) will be exactly same as y). We want the model to generalize.
Choosing the learning rate (η) in Gradient Boosting involves a classic bias–variance–compute trade-off:


#### Very Small η (e.g. 0.01 or lower)

Pros
 Stable learning: each tree makes only a tiny correction → less risk of overshooting optimal fit.
 Lower variance: model is less likely to chase noise → better generalization.
 Safer with deep trees: you can grow somewhat larger trees without easy overfitting.
Cons
 Slow convergence: you need many more trees to reach the same training error → longer training time.
 Under-training risk: if you hit your iteration limit (or time budget) before converging, you may underfit.
 Higher computation cost: more trees = more memory, more inference overhead at prediction time.


#### Very Large η (e.g. ≥0.2 or higher)

Pros
 Fast convergence: each tree makes big corrections → you need far fewer trees to fit the data.
 Lower compute/time: fewer boosting rounds → quicker training and smaller ensemble size.
Cons
 High variance: big updates can “overshoot” the optimum, oscillate, or diverge.
 Overfitting risk: the model may fit noise in early rounds and never recover, hurting test performance.
 Sensitivity to tree depth: with large η, even shallow trees can overfit, forcing you to aggressively prune or limit depth.
Đối với những dạng bài có Stepsize:
Gamma: is the optimal leaf weight (or step‐size) found by minimizing the loss once you’ve picked your stump h1(x). It tells you “how far” you should move F along the direction h1 to best reduce the loss.:
Giả sử: The weak learner is a decision stump that splits on ImageScore>=4.
For regression/continuous with MSE loss:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_102_ff580157.png|ff5801576b986179b9875f9d762b198b [END_IMAGE_PATH]
y_i: target label; S+: set of rows where the tree predicted on ImageScore >=4
For categorical with line search method and log-loss:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_103_28712c3c.png|28712c3cf2d493f6c7fa1f58d18258b9 [END_IMAGE_PATH]
m là số row đc cây split trên ImageScore >= 4, n là số row ImageScore < 4
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_104_5f8fbc86.png|5f8fbc861e27b768751254e6e5e09c6d [END_IMAGE_PATH]
Đây là công thức update khi có cả LR và Stepsize (optimal left weight)
Loop 1:
Step 1:Recalculate Residuals
Once we have new predictions F1(x) we calculate new residuals.


### PCA/SVD

PCA is a dimensionality reduction technique. It helps us simplify data by keeping the most important information and removing redundancy. Imagine you have a dataset with 100 features (columns), and you want to reduce it to just 2 or 3 without losing much of its essence — PCA does that.
Intuition: Suppose you're looking at a cloud of points in 3D (x, y, z). If the points mostly lie along a flat plane, then you can compress this 3D data to 2D without much loss. PCA finds that plane.
Key Idea: PCA finds new axes (called principal components) which:
1. Capture the most variance in the data.
2. Are orthogonal (uncorrelated).
3. Let you project your data into fewer dimensions while preserving as much information (variance) as possible.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_105_375038cc.png|375038ccc5c1626f318acb07215e7cbf [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_106_8709575d.png|8709575de17711bb39e81994f58d81f5 [END_IMAGE_PATH]


#### Understanding Linear Transformations

 In optimization, neural networks, and other algorithms, matrices often represent transformations. Eigenvectors help analyze how these transformations behave.
 For instance, in analyzing weight matrices in deep learning, the largest eigenvalue can indicate the stability or instability of training (e.g., exploding gradients).


#### Covariance Matrices & Variance Structure

We often compute covariance matrices to understand how features vary together.
 Eigenvectors of the covariance matrix tell you the axes (directions) of variance.
 Eigenvalues tell you how much variance lies along each direction.
So instead of looking at raw features, you can rotate the space (using eigenvectors) to find a cleaner, more informative representation of the data.
We care about eigenvectors in ML because:

[START_TABLE_CONTENT] | Property | Why it matters in ML |
| --- | --- |
| No rotation, only scaling | Stable, interpretable transformations |
| Encodes main variance directions | Helps reduce dimensions without losing key patterns |
| Tells how matrices behave | Useful in optimization, stability, regularization |
| Encodes graph structure | Used in spectral clustering and graph ML | [END_TABLE_CONTENT]


#### PCA concept

 PCA finds the eigenvectors of the data covariance matrix.
 These eigenvectors (called principal components) represent directions of maximum variance in the data.
 Eigenvalues tell you how much variance is in each direction.
 You project data onto a few top eigenvectors, reducing dimensions but preserving most of the information.
💡 So here, the eigenvectors tell us which directions carry the most information. They don’t rotate — just scale the data — which makes the transformation stable and interpretable.
Let’s say your 2D data is aligned in the direction of v=[2,1]:
 That direction is very important because it remains consistent under transformation — like a principal component in PCA.
 The eigenvalue λ=5 tells you how strong the transformation is in that direction.
 If eigenvalue were < 1, it would shrink. If > 1, it stretches.
PCA: emphasize encode → center → covariance → eigen → project
Covariance matrix: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_107_d7255496.png|d725549663c1becdf0aa1fb3ee0eb319 [END_IMAGE_PATH]
Eigenvalues and Eigenvectors:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_108_8477976f.png|8477976fb49802cae44a60d804b468d7 [END_IMAGE_PATH]
This is also the first PCA axis. Calculate v2 will be the second PCA axis.
We choose the 1st eigenvector to project since it is more significant (based on the eigenvalue)
Projection: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_109_4ebd9c27.png|4ebd9c27a000e17d774a0f34f53dea1a [END_IMAGE_PATH]
Example: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_110_194efc8c.png|194efc8c75511bbfcbe1724ccf2951dc [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_111_e9e8d59a.png|e9e8d59a1703a634a09329fd7e5cd3e0 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_112_8ff889d5.png|8ff889d5a3356e68f74cc14a5abe4714 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_113_6bd4a03e.png|6bd4a03e83959deb9fd4add05db37db0 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_114_f0bed681.png|f0bed68171925446827896fb85cfbdd8 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_115_608732f6.png|608732f6fa6edfb57c81385eebead455 [END_IMAGE_PATH]


### HMM-CRF

HMM:
- Terminology:
A: Transition matrix: How hidden states change over time
B: Emission matrix: How observations relate to hidden states
- HMM Task: Inference, sequence prediction, likelihood estimation
- Viterbi: used for determining the Most likely sequence of hidden state, given the observation sequence.
π = [0  1  0] (initial state is M with probability 1), Observation: A->B->C->D
δ₁(i) = π(i) * bᵢ(A)
δ₂(j) = maxᵢ [δ₁(i) * aᵢⱼ] * bⱼ(B), ψ₂(j) = argmaxᵢ [δ₁(i) * aᵢⱼ]
δ₃(j) = maxᵢ [δ₂(i) * aᵢⱼ] * bⱼ(C), ψ3(j) = argmaxᵢ [δ2(i) * aᵢⱼ]
δ₄(j) = maxᵢ [δ₃(i) * aᵢⱼ] * bⱼ(P), ψ4(j) = argmaxᵢ [δ3(i) * aᵢⱼ]
- Forward algorithm: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_116_b2d4b174.png|b2d4b174642280f3859e800dff7ed089 [END_IMAGE_PATH], used for determining the probability of the observation sequence happened.
CRF:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_117_4504730b.png|4504730b7c59291e9afffcc6d9be865e [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_118_e4d52474.png|e4d524742eb754a2d261c90a0ef36545 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_119_886aecb4.png|886aecb4a3f5f8084328f4f1270fd812 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_120_256886bb.png|256886bbae8476e1fcea4333aae30a3a [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_121_7760432e.png|7760432e47d56e90fac14189d85d32cd [END_IMAGE_PATH]
Need: Transition feature functions f(yt-1,yt), Feature functions f(yt,xt) and their respective weights, sequence of y including initial state y_0.
Calculate unnormalize score: Calc. unnormalize score at every time step then sum them up.
Calculate normalized score: exp(unnormalize score)
Calculate global normalization Z(x): Sum of every normalized score of all paths from initial state
Calculate probability: P(The Sequence of y | x) = Normalized score(that sequence) / Z(x)


### Generative vs Discriminative model

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_122_fe655a03.png|fe655a03d1c8559c8989886a39c6fec9 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_123_89ed7c76.png|89ed7c766481a3497c0899c605789b01 [END_IMAGE_PATH]
- CRFs were invented to eliminate the need to assume independence between the different observation features (HMM property).
- CRF is available when we get to combine multiple, heterogeneous signals
CRFs directly estimate the conditional distribution P(y∣x) without modeling how the inputs x themselves are generated. Because they focus all modeling capacity on the boundary between labels, discriminative models typically include many overlapping features of the input, each with its own weight, increasing the model’s flexibility—and its variance.
In contrast, generative models impose stronger structural assumptions (e.g. fixed emission distributions in HMMs), which act like a form of built-in regularization and often require fewer free parameters, reducing overfitting risk
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_124_3d85576e.png|3d85576e9ad8e505fe46a8124f5c92fa [END_IMAGE_PATH]
 HMM is a good fit when you need to generate sequences or when you believe its simple emission + transition model suffices (e.g. speech synthesis, DNA sequence modeling).
 CRF excels when you care only about labeling and want to leverage rich, overlapping features of the entire observation sequence—yielding typically better accuracy in NLP tagging or biological-sequence annotation.


## 2. Natural Language Processing


### 1.1. Preprocessing

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_125_d8c87cf5.png|d8c87cf5db28138dc3a02a5795b90e2e [END_IMAGE_PATH]
﻿Text Data Preprocessing Techniques:
- Noisy entity removal:  HTML tag, Convert to lowercase (lower()), Remove punctuation and whitespaces (replace() with regex), Remove stop words (use NTLK library),
- Text Normalization: Standardize text (abbrev/teencode -> standard), Correct spelling (use textblob library), Tokenization(﻿For English: NLTK, SpaCy, TextBlob; For Vietnamese: VnCoreNLP, underthesea, coccoc-tokenizer),
- Word standardization: Lemmatization and stemming (NLTK/TextBlob)
﻿  + Stemming: ”fishing”, ”fishes” -> ”fish” (Removes prefixes/suffixes)
+ Lemmatization: ”good”, ”best” -> ”good” (considers semantics)
- Explore text data (word count, word frequency, distribution of words, word cloud -> NLTK/TextBlob)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_126_36ddf4ad.png|36ddf4ad9499853d896ea0502485a9d7 [END_IMAGE_PATH]


### 1.2. Language model

﻿A language model is a model that predicts the probability of a sequence of words. ﻿
P(W) = P(w1, w2, . . . , wn)
﻿Example
S1 = ”The cat jumped over the dog.” ⇒ P(S1) ≈ 1
S2 = ”The jumped cat the over dog.” ⇒ P(S2) ≈ 0
Application: ﻿
- Machine Translation: P(high winds tonight) > P(large winds tonight)
- Text Correction
- Speech Recognition: P(I saw a van) > P(eyes awe of an)
- Handwriting Recognition: P(Act naturally) > P(Abt naturally)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_127_cbb4ee30.png|cbb4ee3053944670d81a3cb839182685 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_128_09485243.png|094852436c18aa2ac14d3ff8ffba76da [END_IMAGE_PATH]
N-gram model: ﻿probability of a word dependent on N previous words
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_130_9ca09ed0.png|9ca09ed039c04712506a7d59a854e816 [END_IMAGE_PATH]
Unigram (prob of a word independent to other previous words): [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_129_f733861d.png|f733861d1ac5a9708fa1a837fb0112a9 [END_IMAGE_PATH]
﻿Likelihood Estimate of Bigram (2-gram): [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_131_fd0c6a4e.png|fd0c6a4ed1894355f0201bddccabc3b2 [END_IMAGE_PATH]
Trigram:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_132_abb4a82c.png|abb4a82cb618ebc689054f96c99c167e [END_IMAGE_PATH]
Best n-value: n=3 is common (n=4->too large; n=inf -> perfect model but time is also inf).
﻿
Shannon Visualization Method: Choose a random bigram (<s>, w) according to its probability. Now choose a random bigram (w, x) according to its probability. And so on until we choose </s>. Then string the words together
Smoothing:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_133_7ea2ca6f.png|7ea2ca6f8d7e3c263ac473f473610f8a [END_IMAGE_PATH]
Smoothing technique: GoodTuring, WittenBell, Kneser-Ney, Backoff
﻿Huge Language Models and Stupid Backoff:
- Solving large-value problems, e.g., Google N-gram corpus
- Pruning: Only store N-grams with frequency > threshold; Remove higher-order n-gram entries
- Effciency:
+ Use tries (efficient);
+ Bloom filters: approximate language model matching;
+ Store words as indices, not strings (Use Huffman coding to convert large words into 2 bytes)
+ Probability quantization (4-8 bits instead of 8-byte float)
Stupid backoff algorithm helps the model maintain a manageable size while still achieving reasonable effectiveness
Perplexity: Model evaluation (used in task ... and model ... )
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_134_baab6b43.png|baab6b4345e9eaead8fdce794728b925 [END_IMAGE_PATH]
Conditional Language Model: models the conditional probability of a sequence of tokens given some additional information.
A conditional language model estimates:
P(Y∣X)
 XXX: input (e.g., a sentence, question, or image)
 YYY: output sequence (e.g., a translation, summary, or answer)
In machine translation: P(French Sentence∣English Sentence
In question answering: P(Answer∣Context + Question)
Use maximum likelihood estimation -> Overfitting, OOV items (Zero-Prob), Unreliable estimates when there is little training data


### 1.3. Vector Semantics and Embeddings

Useful features can be manually engineered (feature engineering)
- Statistical features: length, position, etc.
- Using scores from dictionaries: Sentiment dictionaries: SentiWordNet, SentiWords, etc.; Subjectivity/objectivity dictionaries: MPQA
- Syntactic features: POS tags
Feature Vector: Value of some features from an observation can be represented as a vector. Features will be useful in distinguishing between categories.
Vectorization is the process of transforming text documents into numerical feature vectors.
Bag of Words (BoW): a strategy of tokenization, counting and normalization that uses CountVectorizer (builds a dictionaries and stores their frequency). However: ﻿BoW model does not effectively represent the order of words → use N-grams
﻿Co-occurrence Matrix: Counts the co-occurrence of words in a matrix. Co-occurrence word statistics describe words that frequently appear together, representing relationships between words.
The statistical process involves counting the occurrences of words in a text corpus.
Tính chất: là 1 ma trận đối xứng. Các chữ gần nhau sẽ +1 vào 2 vị trí
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_135_2d53941d.png|2d53941d8d29956b7f8d34ead9dc53c5 [END_IMAGE_PATH]


#### TF-IDF: weighing terms in the vector

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_136_da0dfabb.png|da0dfabbf899f070ce3ce4c1a85f1f14 [END_IMAGE_PATH]
=> Equal TF weighting: thay vì xài BoW ta xài BinaryWord: nếu có xuất hiện thì =1, ko xuất hiện thì =0, ko quan trọng frequency
=> Nonequal TF weighting: xài BoW. Sẽ là equal TF weighting nếu trong document mỗi từ xuất hiện chính xác 1 lần.
To compute the cosine similarity between Document 1 ("Lions eat fat cats.") and Document 2 ("Cats eat fat mice.") using equal term frequency (TF) weighting:
Step 1: Build the Vocabulary: Identify all unique terms across both documents: [cats, eat, fat, lions, mice]
Step 2: Create Term Frequency Vectors
Document 1 Vector: [1, 1, 1, 1, 0] = A->|A|=2
Document 2 Vector: [1, 1, 1, 0, 1] = B->|B|=2
-> Cosine sim = AB/|A||B| = 3/4 = 0.75.


#### Word2Vec model

﻿﻿Why dense vectors instead of sparse
=> Short vectors may be easier to use as features in machine learning (fewer weights to tune)
Dense vectors may generalize better than explicit counts
Dense vectors may do better at capturing synonymy: car and automobile are synonyms but are distinct dimensions; a word with car as a neighbor and a word with automobile as a neighbor should be similar, but aren’t


#### CBOW vs Skipgram vs Glove

CBOW: You're given the context words and you try to predict the center word.
Objective: maximize likelihood  [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_137_2010284d.png|2010284d8c2ba19f98b37ad4afbe9ca6 [END_IMAGE_PATH]
Example: “the cat sat on the mat”, Context Window: 2. Need to Predict “sat” from context: [“the”, “cat”, “on”, “the”]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_138_e2de4440.png|e2de444080ddf2e925d7f2ea652eafdf [END_IMAGE_PATH]
x_i is sparse vector -> they get multiplied with embed matrix W(1) to get dense word vectors -> averaged (bow assumption-ignore order) -> project to vector size |V|-> softmax for that vector
Note that to stabilize softmax output: Subtract the maximum value from all logits (common trick for numerical stability): Zi = Zi - max(Z) then use softmax on Zi, i=1,n
Skip-Gram: You're given the center word and you try to predict the surrounding words.
Objective: maximize likelihood [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_139_94b4e1b3.png|94b4e1b31522219f465bcd0d2dfae60b [END_IMAGE_PATH]
Example: “the cat sat on the mat”; Context Window: 2. Need to Predict context [“the”, “cat”, “on”, “the”] from center “sat”
Training Process: Embed the center word -> Use it to predict each context word independently via softmax.

[START_TABLE_CONTENT] | Model | Pros | Cons |
| --- | --- | --- |
| CBOW | Faster training on large corpora, works well with frequent words | Averages context → may lose order/nuance |
| Skip-Gram | Used when having rich vocab. Captures rare word relationships better | Slower, especially with large vocabulary | [END_TABLE_CONTENT]

Glove (global vector): "How often do two words appear together in the whole corpus?"
Objective:
Factorize a global word-word co-occurrence matrix into lower-dimensional embeddings.
-> Fast training, Stable quality on large datasets, Good results even with small datasets and vectors. But requires a lot of memory (to compute co-occurence matrix, thus is not suitable for streaming data) and can be affected by the initialization process of the ”learning rate”. Use when you want embeddings that encode global corpus-wide statistics, or need strong semantic relationships.


### 3. Deep Neural network

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_140_3370c502.png|3370c502805b370a135e70cd4591194a [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_141_ca61bf87.png|ca61bf87cd8b26623ddef03cf652c1a4 [END_IMAGE_PATH]
Why we need Activation function:
Softmax vs sigmoid vs tanh vs relu vs elu
Time and space complexity of forward prop:
Backward =Forward prop: O(L*n^2) (n: số node ở mỗi layer aka num features, L: số layer)
Why we calculate loss using backward prop and not forward prop:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_142_426beae5.png|426beae5c9a88b074464c2899b5b2daf [END_IMAGE_PATH]
if each z(i) or a(i) has n dims, each Jacobian has n x n dims => matrix multiplication is n^3
Loss function of NN: negative log-likelihood or BCE
optimizer of NN: SGD
Stanford Questions:
﻿A 2-layer neural network (aka input-hidden-output layer) with 5 neurons in each layer has a total of 60 parameters (i.e. weights and biases) -> True (5x5+5x5=50 weights, 5+5=10 biases)
﻿Which of the following is true about the vanishing gradient problem?
(Circle all that apply)
(i) Tanh is usually preferred over sigmoid because it doesn’t suffer from vanishing gradients
(ii) Vanishing gradient causes deeper layers to learn more slowly than earlier layers
(iii) Leaky ReLU is less likely to suffer from vanishing gradients than sigmoid
(iv) Xavier initialization can help prevent the vanishing gradi ent problem
(v) None of the above
﻿Consider a trained logistic regression. Its weight vector is W and its test accuracy on a given data set is A. Assuming there is no bias, dividing W by 2 won’t change the test accuracy => True
﻿
The gradient estimated during a step of mini-batch gradient descent has on average a lower bias when the data is i.i.d. (independent and identically distributed). True or False? Explain why.
Solution: True. The examples in a batch should be i.i.d. because mini-batch
gradient descent uses an empirical estimate of the gradient from a small batch. If
the examples are correlated, then the gradient estimates will become biased and
the model will fail to learn.
You have two data sets of similar size for a binary classification task. However, one contains almost entirely positive examples, and the other contains only negative examples. You would like to use both sets to train your model. Describe a scenario in which combining these two data sets could lead to a failure of the model to learn.
﻿Solution: Imagine training on mini-batches constructed from dataset 1 (mostly positive examples, then training on mini-batches from dataset 2 (only negative examples). The model will likely forget what it learned from the positive examples and will learn to always predict negative examples.
Why do the layers in a deep architecture need to be non-linear?
﻿Solution: Without nonlinear activation functions, each layer simply performs a linear mapping of the input to the output of the layer. Because linear functions are closed under composition, this is equivalent to having a single (linear) layer. Thus, no matter how many such layers exist, the network can only learn linear functions.
﻿Name one advantage of using ELU over ReLU.
Solution: Non-zero gradient everywhere avoids dying ReLU problem
Which of the following statements are true about gradient descent (GD)? (Tat ca deu dung) (A) Increasing the step size/learning rate of GD may help GD converge faster.
(B) Increasing the step size/learning rate of GD may cause it to not converge at all.
(C) GD (with a suitable step size) will converge to an approximate stationary point, even for non-convex functions.
(D) GD can be used to solve logistic regression
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_143_64fea515.png|64fea5152138f0a073cb4f92359495cb [END_IMAGE_PATH]


#### CNN - CONVOLUTIONAL NEURAL NETWORK

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_144_f1e5b5ff.png|f1e5b5ff0ad89c6e52dabe690ed6524a [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_145_b2c71488.png|b2c71488fd177e1c8098b9758132e2af [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_146_2e83855c.png|2e83855ce634c7d899c614cd441c7d67 [END_IMAGE_PATH]
Bigrams carry local meaning (is great = positive, is bad = negative)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_147_bac8d9de.png|bac8d9defa26a89328d38f3999e83ca8 [END_IMAGE_PATH]
For pooling, only the position with max element will contribute to the final prediction and to the loss.
Max Pooling in Backward Pass: The gradient flows back only to the position that had the max value in the forward pass. All other positions get zero gradient.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_148_4052ecf7.png|4052ecf7cdc775fb573183775fd17917 [END_IMAGE_PATH]
=> Limitation of Max Pooling: It ignores partial evidence — only strongest activations contribute to learning.
That's why in practice, Average pooling can be used when you want every position to contribute
Or global max pooling is combined with many examples so filters train from different positions over time
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_149_fe38a207.png|fe38a207906f3e874712cc1e2a22c98c [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_150_dc135815.png|dc135815dbd30973671b26c879f702f3 [END_IMAGE_PATH]
One filter (matrix of weights) is shared across all input positions. Filter weights are shared across time.
Filter shape is (filter_height, embed_dim) = (2,N) since we extract bigram, the filter span 2 words


##### Convolutional Formula

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_152_ebad8510.png|ebad8510c526e1846ec410014316289b [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_153_828e110e.png|828e110ec8af75ff9424c22a88afc153 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_154_d9ed3a4d.png|d9ed3a4d5841fc24e486e3733870983c [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_155_b9036a0f.png|b9036a0f47ba48a3db9c3b7e91993bdf [END_IMAGE_PATH]
Max Pooling: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_151_de985438.png|de9854388e6046d67aa0e902192e4d24 [END_IMAGE_PATH]
FeedForward the candidate bigram:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_157_b21cb3cf.png|b21cb3cf5a0fa9cf0802d68cfd0316b6 [END_IMAGE_PATH]
Calculate Loss: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_156_959a6001.png|959a6001b45f9128b38dd2806acc64af [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_158_f16be94c.png|f16be94ce4ffde23a6e600eeedb96be4 [END_IMAGE_PATH]We have 2 sentences => use avgloss
Backward pass: Use Mini-batch GD (batch size = 2):
For FFN weights
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_160_37850b67.png|37850b67f17abc1bb699558408e65941 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_161_b396bc10.png|b396bc1039de4b74c03529341c147a9d [END_IMAGE_PATH]
For Filter weight:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_159_f4548994.png|f4548994290ccaec6fd4065ad7828fb1 [END_IMAGE_PATH]
(Calculate all w_ij1..2 for both sentences. Then take the average wij = (wij1 + wij2) /2
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_162_33a66460.png|33a664603298fa0cd6a5ab8150ce682b [END_IMAGE_PATH]For "This movie is great", region "is great"
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_163_f25446d6.png|f25446d65b061831d1e525f3e86e8910 [END_IMAGE_PATH]For "This movie is bad", region "Movie is"
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_165_aaf924d7.png|aaf924d72c5710d73aa44232268466c6 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_166_64b7096d.png|64b7096d85ac803b0417b46093fa5daa [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_164_34de100a.png|34de100a7747f32fbf0556731e36f163 [END_IMAGE_PATH](Same with FFN bias)


#### 4.1. RNN

Input thuong la: (Batch size, length(num token), dimension)
Problem of zero-padding for variable-size sequence input: does not svale well with very long seqs
=> Fix: thay vì bỏ toàn bộ input vào layer, ta bỏ mỗi input 1 layer. Tương tự, mỗi output 1 layer
=>﻿ it tinh toan hon nhung so luong weight phai hoc co the gan bang max length
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_167_8e345a2d.png|8e345a2d2c6fb3efa59e3369caadfa9c [END_IMAGE_PATH]
﻿
RNN sử dụng cùng 1 bộ weight cho các token của 1 sequence => ﻿RNNs are just neural networks that share weights across multiple layers, take an input at each layer, and have a variable number of layers. It extends standard NN along Time dimension
Graph­structured backpropagation (Reverse­mode automatic differentiation):
For each node with multiple descendants in the computational graph, simply add up the delta vectors coming from all of the descendants
﻿What makes RNNs difficult to train? => they are extremely deep networks
﻿vanishing gradients = gradient signal from later steps never reaches the earlier step => prevent RNN from remember things at beginning => cannot fix with gradient clipping
exploding gradients -> fix with gradient clipping
=> both can be avoided by letting gradient close to 1
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_168_0a3ca852.png|0a3ca852924393d7bdd2dc46ff12a6ed [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_169_9882ac32.png|9882ac322d6ec37cd2489cb6168872c0 [END_IMAGE_PATH]


##### When we need to forget?

-> past information is no longer relevant to the current prediction.
Example: “I went to the restaurant. The food was amazing. Later, I walked to the park. The trees were tall.”
Forgetting the past also help model not be distract by long-age info and focus more on short-term frequencies, making training more stable
=> LSTM cell (4x larger in dimensionality than RNN cell -> 4x computes)
- Keeps cell state c_t to store memory
- Learns what to remember, what to forget, what to output
- 3 gates: Forget, input, output
Why LSTM train better: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_170_56d67c38.png|56d67c388c1b2c1a61d9254348d3a999 [END_IMAGE_PATH]
Variant of LSTM: GRU (simpler) - No separate cell state. But performance is near LSTM. Has 2 gates: Update and reset.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_171_a2d89405.png|a2d894056ce9775eee5b8d5838824a87 [END_IMAGE_PATH]
(To prevent "Sai 1 đằng đi 1 nẻo"). Ví dụ: Câu đúng là I like machine learning
Input: I, Predicted: think. Thì predicted sequence là I think. Nó sẽ tiếp tục predict dựa trên thằng "I think" thay vì "I like" -> Deo on roi
Training/testing discrepancy: ﻿the network always saw true sequences as inputs, but at test­time it gets as input its own (potentially incorrect) predictions
This is called distributional shift, because the input distribution shifts from true strings (at
training) to synthetic strings (at test time) (simpler language: The model is trained on inputs from the true data distribution, but is tested on inputs from its own predicted distribution)
Even one random mistake can completely scramble the output!
=> Solution: Schedule sampling: Slowly mix in the model’s own predictions as inputs during training, so it learns to handle its own errors. This originates from an old trick from Reinforcement learning
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_172_c7107fa8.png|c7107fa893a109cdc5a4721696fd3d7a [END_IMAGE_PATH]
(aka: during training, at beginning, feed ground truth tokens. At near end, feed the model's own prediction (you see what you do!)


##### Different ways to use RNNs

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_173_ecc56323.png|ecc5632379e815ba76449b8878c54f7f [END_IMAGE_PATH]In Unidirectional model (left to right): fine for tasks like language modeling (predict next word)
Problem:  ﻿the word at a particular time step might be hard to guess without looking at the rest of the utterance! (for example, can’t tell if a word is finished until hearing the ending)
Tasks like NER, POSTagging, sentiment analyze, machine translation, summarization: must look from past and future!
Questions:
1. Why BPTT has problem with vanishing/exploding gradients?
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_174_ca8e161c.png|ca8e161ce104900f4276976d241a94e6 [END_IMAGE_PATH]BPTT is backpropagation applied to RNNs by unrolling them through time — treating each timestep as a layer in a deep feedforward network. So a 10-word sentence becomes a 10-layer deep network in time.
Vanishing Gradient: when weights & activations < 1, small gradients multiply repeatedly → shrink to near-zero => early timesteps get no learning signal
Exploding gradient: when weights >1, Multiplication causes gradients to blow up exponentially = lead to numerical instability
Fixes: Use ReLU or gated units (e.g. LSTM/GRU); Gradient clipping (for exploding); Layer normalization
2. Why RNN is suitable for machine translation problems? How can it be leveraged?
Machine Translation = converting a sequence in one language to a sequence in another (e.g., "I love AI" → "Tôi yêu AI") => RNN strength:
Sequential processing => Natural fit for word-by-word understanding
Shared hidden state => Maintains context of entire sentence
Flexible input/output length => Can translate short or long sentences
Encoder-Decoder structure => Allows separate representation & generation phase
How to leverage RNN: Encoder-Decoder architecture (seq2seq)​


### Seq2Seq

Basically a RNN encoder-RNN decoder model (different weight: W_enc != W_dec)
Normally the encoder will be fed with reverse input
e.g. Un chiot mignon -> A cute puppy
Input for encoder: mignon chiot Un
In reality: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_175_e5875f2c.png|e5875f2c8e43fd7087fdd5d5d18f8cb0 [END_IMAGE_PATH]
Beam search: instead of choosing most probable next word, choose from top-k word SO FAR. Then update each of them (think as if the leaderboard, each layer is an update). Often k=5-10
Greedy search: choose most probable next word
Beam search algorithm:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_176_647f2d49.png|647f2d496c8bab79023e590faf1b1320 [END_IMAGE_PATH]
x_i,1..T -> depends on whole input sequence
y_i,0..t-1 -> depends on output sequence SO FAR
Small issue: Longer sequence -> lower score (imagine 0.6x0.6 vs 0.6x0.6x0.6) -> lower chance to be chosen.=> Solution: Normalize through dividing by sequence length
A RNN architecture diagram for English-Vietnamese translation problem
("I", "love", "AI")                       ("Tôi", "yêu", "AI")
x1       x2       x3                               y0       y1      y2
|         |         |                                     |          |         |
|         |         |                                    ↓         ↓        ↓
↓        ↓       ↓                            [START]  "Tôi"  "yêu"
h0 -->  h1 -->  h2 -------------------> c --> s1 -->  s2 -->  s3
Encoder RNN                                ↑       Decoder RNN
(context vector c = h2)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_177_5c9c8e77.png|5c9c8e7704d5a7e15387855955f56442 [END_IMAGE_PATH]
Encoder: Encodes source seq. into context
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_178_bc442e99.png|bc442e9907690ab54694ae6930e1c183 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_179_83bd0a78.png|83bd0a78d14f31d4297fccacf58fee5b [END_IMAGE_PATH]
Decoder: Generate target Seq from context
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_180_55ac87ab.png|55ac87ab8a399b38e5870c3b29c2bf7f [END_IMAGE_PATH]. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_181_70ea4a84.png|70ea4a844719f115271f8b1e272f1c1d [END_IMAGE_PATH]
Wxh: shape là Hidden x Input embed
Whh: shape là Hidden x Hidden
Why (or Wy_dec): shape là Output-vocab-size x Hidden
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_182_edd5fd8b.png|edd5fd8b7c6f367ea34ec13db6f7e10b [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_183_e6119771.png|e61197714eebca7f41615ed3d4bcd2e8 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_184_e302e8f5.png|e302e8f51ac07eeeab37f05367b52b00 [END_IMAGE_PATH]
Quy trình:
1. Forward Pass
1.1 Encoder: Đề cho h_0 enc = 0. Tính  h_1 enc, h_2 enc, h_3 enc (basically h_enc for all time step t)
Lưu ý: Shape của h_enc là Hidden x 1, vì x_t là Input embed x 1
1.2 Decoder: Tính h_0 dec = h_3 enc, h_1 dec, y_1 dec, h_2 dec, y_2 dec, h_3 dec, y_3 dec, h_4 dec, y_4 dec, h_5 dec. Không tính y_5 dec vì y_4 dec theo Teacher forcing đã là EOS
LƯU Ý 1: Khi tính h_n dec với n>=2 trở đi, ta xài y_(n-1) dec chuẩn Ground Truth (Teacher forcing)
LƯU Ý 2: softmax tại time step t=t0 có kết quả a0,a1,a2,a3 tương ứng với Tôi, Thích, Sách, EOS. Cái nào cao nhất thì model predict cái đó.
LƯU Ý 3: Shape của h_dec là Hidden x 1, Shape của y^ = y_dec là Vocab_size. Bởi vì ta pick max num trong vector chứa các vocab.[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_185_d61a5ed4.png|d61a5ed4cd30cbc8cb99f51831fb3996 [END_IMAGE_PATH]
1.3 Tính CE loss
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_186_2e9f2a05.png|2e9f2a05b98e7df4eca766fba4a81c8d [END_IMAGE_PATH]
2. Backward Pass
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_189_5717f0d4.png|5717f0d45393598a5156cd3cd44701da [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_187_6151e2f0.png|6151e2f0a41c8707a9fae891dc09592f [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_188_76ee10f9.png|76ee10f9fb28d5637fde66c9d889b5c6 [END_IMAGE_PATH]Mẹo: Tính theo từng time step cho các gradient rồi thực hiện phép cộng. PHÉP CỘNG LÀ PHÉP CUỐI CÙNG
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_190_3969aed5.png|3969aed58dc18d7d672a5fd29f84d5a9 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_191_fa6f3c46.png|fa6f3c46659f5a73d303e5964aa4e0d9 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_192_0efa343f.png|0efa343fb090f04b79d599e8314c140f [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_193_0f1d9a57.png|0f1d9a57143fcfa093b6f6188d07c947 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_194_7f9d511e.png|7f9d511e9f739168edf067d2285b603b [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_195_c03d05d3.png|c03d05d3b9ca86dab8b6feb9b54be8f2 [END_IMAGE_PATH]
Đôi lúc chỉ yêu cầu tính cho Last time step (không cần sum over all time steps). This is common in tasks like: Sentiment classification (only compute loss at final token), and One-step prediction tasks (predict one word based on a whole sentence). Nếu sum over thì đó là autoregressive language modeling (predict next token for every position)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_196_68b4fbfe.png|68b4fbfe95161d09001516930abebe5e [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_197_847770f1.png|847770f11f6690326bc8bc6e97f1369c [END_IMAGE_PATH]


### Attention

- Solve the bottleneck problem: ﻿all information about the source sequence is contained in y_0 only
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_198_da4e09fc.png|da4e09fccc925b5f4d8245338dd841f1 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_199_0345d5aa.png|0345d5aa709202e75a55e365022a14b4 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_200_9479d608.png|9479d60826556168a1518d67dc83add8 [END_IMAGE_PATH]
if there are n 'h' and m 's' => n*m attention score
Attention variant: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_201_aed092e8.png|aed092e864f6e96558027897b9ad43f6 [END_IMAGE_PATH]
Or: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_202_f41d1d67.png|f41d1d67684118cd2d14456bbb44185e [END_IMAGE_PATH]
Or: [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_203_f38a28e9.png|f38a28e957ed03e08a7872f5a3afa7ff [END_IMAGE_PATH](Not non-linear attention)


#### Self-Attention

1.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_204_a3b92819.png|a3b928199bbdfaa8f94263066dc62bbf [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_205_1610c30e.png|1610c30e5e3ce616e8ae0df4f3605b9f [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_206_adbb194d.png|adbb194d972e9d09b9ee38a94b7836de [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_207_d5dbdb0c.png|d5dbdb0cbe02d4fcbde24978acb76cbc [END_IMAGE_PATH]
Softmax-Rowwise
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_209_3f1f0755.png|3f1f075571010fc270afd0ac3e1f1e52 [END_IMAGE_PATH]
After get the attention_output (seqlen, d_model), insert it to FFN layer. [START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_208_fd733abb.png|fd733abbb5e470067e6dc3621ada82a9 [END_IMAGE_PATH]
The output is a matrix of (seq_len, vocab_size). It is then softmaxed.
Backward pass:
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_210_d24ab762.png|d24ab7624481c81464a64f91c481530a [END_IMAGE_PATH]
(This is after softmax, so it does not account softmax here)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_211_d7f32d37.png|d7f32d3758612c784e176dddd56e8945 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_212_5e562fed.png|5e562fed3b4c271d687895f3499a2551 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_213_80d85da9.png|80d85da934f3b27aa7f5455598ca5758 [END_IMAGE_PATH]
Lưu ý phép gradL wrtS nhân K1 là nhân ma trận. Sau đó mới nhân 1/dqrt(d_k) là phép scalar x matrix.


#### Masked Self-Attention

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_214_118fbdf2.png|118fbdf28b2e193a52851ee0e7126778 [END_IMAGE_PATH]
Bản chất Mask là phép cộng ma trận S' = S+M
Nếu là masked_self attention thì apply mask sau khi đã normalize Ratio, trước khi apply softmax. Để khi mình apply softmax (bước sau cùng) thì sẽ ra ma trận với nhiều số 0, tức là Token đó không pay attention tới những token sau.
Mask này là 1 matrix (seq_len,seq_len), value=0 nếu current token có thể pay attention (Bản thân nó và những token trước nó). Value = -inf nếun current token không thể pay attention (tức mấy thằng sau nó)[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_215_71e00aca.png|71e00acafd95ecd2f71bf171edefbb99 [END_IMAGE_PATH][START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_216_1b0da527.png|1b0da527554e5529e715446469fcc974 [END_IMAGE_PATH]
Ý nghĩa của attention score:
Với dòng thứ N của attention score matrix, ta có phân phối attention của từ ứng với index N (gọi là X) đối với những từ còn lại (bao gồm bản thân nó). Trong dòng đó, giá trị nào cao nhất thì từ ở vị trí đó là quan trọng nhất đối với từ X.


#### Multi-head Self-attention

[START_TABLE_CONTENT] | Style | Think of it like... |
| --- | --- |
| Split by weight | Each head applies its own lens to the full word meaning. Uses commonly, e.g. BERT,GPT |
| Split by data | Each head focuses on a part of the word’s features | [END_TABLE_CONTENT]

Khi split by weight thì có thể split theo row (trên-dưới) hoặc split theo column (trái-phải)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_217_b47a561e.png|b47a561e92c9797da7ad835e7932c232 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_218_ae3d012d.png|ae3d012d2c9a4f565913bd6b946befe7 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_219_d9e3a0fa.png|d9e3a0fa81256f81efa948a77a4fd785 [END_IMAGE_PATH]
Explanation: different heads specialize in different aspects of relationships in the sequence. Head 1 prioritize in e.g. semantic context while Head 2 prioritize in e.g. capturing positional roles


### Transformer

Positional Encoding (could remove): vì attention score của token h1 ko đổi khi vị trí của nó và các token khác thay đổi, nhưng trong thực tế thì có thay đổi => => Add some info (a function: h_t = f(x_t, t))
Naiive PE: append t to input (ko ổn vì absolute position << relative position)
=> xài sin/cos PE (frequency-based): similar Relative pos have similar PE
=> Better: learn the PE through each time step t (but now every sequence use the same values), need to pick max seq length
Cách xài PE:
- Simple: append p_t to input: [x_t, p_t]
- Popular: emb(x_t) + p_t, with emb(x_t) be some FC layers + Nonlinearities
- Có thể áp dụng PE cho layer đầu hoặc cho tất cả layer
Multi-headed attention[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_220_dcc7091c.png|dcc7091c0e6f60a7e5cacc8cf23988a3 [END_IMAGE_PATH]
=> ﻿ have multiple keys, queries, and values for different positions at each layer for every time step
This is the most crucial component.
Nonlinearities (Position-wise FFNN): đơn giản là thêm 1 FFNN ở tất cả token (VD: sigmoid+linear) ở giữa tất cả layer, because self­attention “layer” is a linear
transformation of the previous layer (with non­linear weights) => self-attention is linear
=> Tạo nonlinear transformation cho mỗi layer
Masked decoding / masked attention: ﻿At test time (when decoding), the inputs at steps 2 & 3 will be based on the output at step 1, which requires knowing the input at steps 2 & 3
=> Must allow self­attention into the past => but not into the future. Như vậy thêm điều kiện cho e = q_l.k_t (l >= t) còn ko thì e = -inf
(Vì masked decoding là component của decoder nên có thể bỏ qua nếu mô hình là encoder-only)
Transformer: a model that entirely based on Self-attention (is attention all we need? => Yes!)
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_221_56b5b6a9.png|56b5b6a92f62cd3b51ceca1b14ad778c [END_IMAGE_PATH]
“Add & Norm” = Residual connection + Layer Normalization
Add: Residual connection: add the input x to the sublayer output
Norm: Apply Layer Normalization to stabilize the signal
﻿➢The “classic” transformer (Vaswani et al. 2017) is a sequence to sequence model
Cross attention: attention between encoder and decoder values is also multi-headed
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_222_5dce9f7a.png|5dce9f7aa6935909c4949b4d33bad98e [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_223_1987da09.png|1987da09801c4f6d65c88c548a6e0721 [END_IMAGE_PATH]
Layer normalization (important):
input 4 chiều:
+ batch size as batch axis,
+ channel (hidden size or num_features) axis,
+ (h, w) as spatial axes; có thể thay bằng seq_len
﻿- Batch normalization is very helpful, but hard to use with sequence models
- Sequences are different lengths, makes normalizing across the batch hard
- Sequences can be very long, so we sometimes have small batches
=> Simple solution: “layer normalization": normalizes across the channel/feature dimension.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_224_b075c3ee.png|b075c3ee662d0c324292b119ee864604 [END_IMAGE_PATH]
﻿Ví dụ: (B,Len,D)=(2,3,4)
- layer norm: tinh tren D (num feature)
- batch norm: tinh tren B
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_225_b3d6c9aa.png|b3d6c9aa529fb4c543fae0d2614c5787 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_226_ee5c3882.png|ee5c3882ab28b8942a24de41a4926766 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_227_87bac552.png|87bac552b4b65ba9820159ac1971deb6 [END_IMAGE_PATH]
đặc tính: recentering, rescaling, ko phụ thuộc batch size
Chi phí tính toán cao: LayerNorm cần tính trung bình (( \mu )) và phương sai (( \sigma^2 )) trên toàn bộ neuron trong một lớp. Điều này làm tăng độ trễ, đặc biệt trong các mạng lớn như Transformers.
Re-centering không cần thiết: Nghiên cứu chỉ ra rằng re-centering không đóng vai trò then chốt trong việc ổn định hoặc cải thiện hiệu quả huấn luyện. Điều này gây ra chi phí không đáng có.
LayerNorm có thể làm giảm tốc độ hội tụ (slower convergence)


## 3. QA About Neural Network (MLP-RNN-LSTM-Transformer-CNN)


### Perceptron (Single-Layer)

1. What is a Perceptron? -> A Perceptron is a binary linear classifier that maps input features x∈Rn to a binary output using a weighted sum and a threshold activation (usually sign function).
2. What is the decision boundary of a Perceptron?
A hyperplane defined by w⊤x+b=0, where w is the weight vector and b is the bias.
3. What is the update rule in the Perceptron learning algorithm?
If y^≤0, update:w←w+ηyx,b←b+ηy where η is the learning rate.
4. What kind of problems can a Perceptron solve?
Only linearly separable binary classification problems.
5. What are the limitations of a Perceptron?
Cannot solve non-linearly separable problems (e.g., XOR)
No hidden layer; limited representational power
6. What activation function does a Perceptron use?
Typically the sign function or Heaviside step function: y^=sign(w⊤x+b)
7. Is the Perceptron algorithm guaranteed to converge?
Yes, if the data is linearly separable. Otherwise, it will oscillate indefinitely.
8. How many parameters does a Perceptron with n inputs have?
n weights + 1 bias = n+1 parameters.
9. What is the geometric interpretation of the Perceptron algorithm?
It tries to find a separating hyperplane by adjusting weights to "push" the decision boundary toward correct classification.
10. What is the learning objective of the Perceptron algorithm?
Minimize the number of misclassifications (not a differentiable loss function like MSE or cross-entropy).
Why can't a single-layer Perceptron solve XOR?
XOR is not linearly separable; there's no straight line (or hyperplane) that separates its classes. Perceptron can only represent linearly separable functions.
6. What is the geometric interpretation of the Perceptron learning rule?
Each weight update moves the decision boundary toward misclassified points, effectively pushing them on the correct side of the hyperplane.
7. What is the role of the bias term in a Perceptron?
It allows the decision boundary to shift away from the origin. Without it, the boundary is constrained to pass through the origin.
8. What is the loss function of a Perceptron?
It doesn't use a differentiable loss function. It performs updates based on misclassification, not based on continuous gradients.
9. Is the learning rate important in Perceptron training?
Yes — it controls the step size of weight updates. However, the convergence of the basic Perceptron is not sensitive to its exact value (as long as it’s > 0).
What are the pros and cons of using sign-based Perceptron?
✅ Pro: Clean theory, margin interpretation (like SVM)
❌ Con: Not compatible with 0/1 label frameworks
11. What are the pros and cons of using step-function Perceptron?
✅ Pro: Compatible with binary classification libraries
❌ Con: Heaviside function is non-differentiable and lacks theoretical margin guarantees
12. What happens if the data is not linearly separable?
The Perceptron never converges, and continues updating weights forever.
When should you not use a Perceptron?
When data is not linearly separable
When you need probabilistic outputs or multiclass prediction
When using large feature sets and need deeper representation
18. Can Perceptron be regularized?
Classic Perceptron doesn’t include regularization. Extensions like margin Perceptron or averaged Perceptron address overfitting.
19. Does Perceptron use gradient descent?
No — the classic Perceptron does not compute gradients or minimize a differentiable cost function.


### Multilayer Perceptron (MLP)

11. What is an MLP? -> An MLP is a feedforward neural network with one or more hidden layers, where each neuron is a perceptron using a non-linear activation (e.g., ReLU, sigmoid).
12. Why is non-linearity important in MLPs?
Without non-linear activation, the entire MLP behaves like a linear transformation, regardless of the number of layers.
13. What types of problems can an MLP solve?
Universal function approximation: MLPs can model any continuous function (given enough neurons/layers).
14. What is the typical architecture of an MLP?
Input layer (features)
1+ Hidden layers (non-linear activation)
Output layer (linear or softmax)
15. How does backpropagation work in MLPs?
It uses the chain rule to propagate errors backward through layers and update weights via gradient descent.
17. How do we compute the number of parameters in an MLP?
Sum of weights and biases across all layers:[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_228_d477d606.png|d477d6066b6fc9c73f19535fbbc296d3 [END_IMAGE_PATH] where n_l​ is the number of neurons in layer l.
18. What are the advantages of MLP over Perceptron? Can solve non-linear problems, Flexible depth and width, Better generalization
19. What are the disadvantages of MLPs? Require large datasets and compute, Prone to overfitting, Vanishing/exploding gradients for deep MLPs
20. What are typical use cases of MLPs? Tabular data classification/regression, Image/sequence preprocessing, Embedding layers in NLP/vision
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_229_2e728491.png|2e7284914946b15edb9534da9283c492 [END_IMAGE_PATH]
How is MLP different from a single-layer Perceptron?
Perceptron: Can only learn linear decision boundaries.
MLP: Can learn non-linear functions via stacked layers and activation functions.
3. What activation functions are commonly used in MLPs?
ReLU: Most common for hidden layers due to fast convergence.
Sigmoid: Used in binary output; suffers from vanishing gradients.
Tanh: Zero-centered, better than sigmoid in many tasks.
Softmax: Used in the final layer for multiclass classification.
Why is non-linearity crucial in MLPs?
Without non-linear activation functions, an MLP becomes equivalent to a single linear transformation, regardless of depth.
5. What does the universal approximation theorem say about MLPs?
An MLP with one hidden layer and non-linear activations can approximate any continuous function on a compact domain, given enough hidden units.
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_230_88ee41a5.png|88ee41a56ad5d3924ee6f006cc641da3 [END_IMAGE_PATH]
Why are MLPs not ideal for high-dimensional inputs like images?
MLPs treat all input features as independent — they do not exploit local spatial correlations. CNNs are better suited for such data.
13. How does depth affect MLP performance?
More layers increase representational power, but may cause: Vanishing/exploding gradients, Longer training time, Overfitting, unless regularized
14. Regularization techniques in MLPs: L2 regularization (weight decay), Dropout, Early stopping, Batch/layer normalization
15. What is dropout and how does it help? => Dropout randomly disables neurons during training with probability ppp, forcing the network to be redundant and robust. It acts as a form of regularization.
16. What is overfitting in MLPs, and how can we detect it?
Overfitting happens when the model performs well on training data but poorly on validation data. Signs include: Training loss → decreasing. Validation loss → increasing
17. What is backpropagation?
=> A recursive algorithm to compute gradients of the loss with respect to weights, using the chain rule from output back to input.
18. What kind of data is suitable for MLPs?
Tabular data (e.g., finance, surveys)
Flattened image or text embeddings
General-purpose classification/regression tasks
19. How do MLPs handle multiclass classification?[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_231_3d715bfd.png|3d715bfdaf768507b6f15a12c89f5cc2 [END_IMAGE_PATH]
Loss: Categorical cross-entropy
20. How does initialization affect MLP training?
Poor initialization can lead to:
Vanishing gradients (if weights too small)
Exploding gradients (if weights too large)
Proper schemes (like Xavier or He initialization) are essential for stable training.


### RNNs

What makes RNNs different from feedforward networks like MLPs?
RNNs have a recurrent connection — they share parameters across time and maintain a hidden state that allows them to model sequences of arbitrary length.
3. What are typical applications of RNNs: Language modeling, Machine translation, Speech recognition, Time series forecasting, Music generation
4. What is the vanishing gradient problem in RNNs?
When backpropagating through time, gradients can shrink exponentially, especially with long sequences. This prevents early layers (earlier timesteps) from learning effectively.
5. How does the RNN learn?
Via Backpropagation Through Time (BPTT): it unrolls the RNN over time and applies standard backpropagation to compute gradients at each time step.
What are the limitations of vanilla RNNs?
Vanishing/exploding gradients
Poor memory for long-range dependencies
Difficulty learning long sequences
What are the pros of RNNs?
Sequence-aware
Parameter-efficient across time
Good for modeling time series and language
17. What are the cons of RNNs?
Difficult to train on long sequences
Slow training (sequential computation)
Forgetful over long contexts
What is BPTT (Backpropagation Through Time)? -> An extension of backpropagation used in RNNs: the network is unfolded across time, and gradients are calculated layer-by-layer backward in time.


### CNNs

1. What is a Convolutional Neural Network (CNN)? -> A CNN is a type of neural network that uses convolutional layers to extract spatial features from structured data such as images or sequences.
2. What is the purpose of convolution in CNNs? -> Convolution enables the model to detect local patterns (e.g., edges, textures) and share weights across space, making the model translation-invariant and parameter-efficient.
What are the key components of a CNN?
Convolutional layers
Activation functions (e.g., ReLU)
Pooling layers (e.g., MaxPool)
Fully connected layers (for final classification)
Batch Normalization
Dropout
What are feature maps in CNNs?
The output of a convolutional filter applied to the input. Each feature map corresponds to a specific learned pattern.
6. What is padding and why is it used?

[START_TABLE_CONTENT] | Type | Description |
| --- | --- |
| Valid | No padding → output shrinks |
| Same | Zero-padding → output same size as input | [END_TABLE_CONTENT]

Padding helps: Preserve spatial dimensions, Prevent excessive downsampling, Let the kernel cover border pixels
What is the role of pooling layers? Pooling (e.g., MaxPool or AvgPool): Reduces spatial dimensions, Provides translation invariance, Reduces overfitting and computation
What activation functions are typically used in CNNs? ReLU (most common), Leaky ReLU, ELU, Sigmoid / Tanh (rare)
What are the disadvantages of CNNs? Requires large datasets and GPUs, Cannot inherently handle temporal dependencies (unlike RNNs), Fixed-size input (unless using adaptive pooling)


### Attention - Transformers

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_232_cdc7e5a3.png|cdc7e5a37c2b8c78e6decf61531dc227 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_233_4878d42c.png|4878d42caf0cdf22f80c13f2b021360c [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_234_48224068.png|482240685ccff416f13c84f8903bd061 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_235_aa1c9399.png|aa1c939939f5c837e0cdaf87344ebba8 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_236_94cd8a28.png|94cd8a28abb6cb9ed4369638a4f6a1b9 [END_IMAGE_PATH]
Recurrent Neural Network (RNN)

[START_TABLE_CONTENT] | Feature | Description |
| --- | --- |
| Structure | Processes input sequentially (one timestep at a time) |
| Memory | Maintains hidden state from previous steps |
| Computation | Not parallelizable across time steps |
| Attention | Not built-in (requires external attention mechanisms for long sequences) |
| Vanishing/Exploding Gradients | Yes, especially on long sequences |
| Positional Info | Implicit (via recurrence) |
| Training Time | Slower due to sequential processing |
| Strengths | Simpler and good for short sequences with strong temporal dependency |
| Variants | LSTM, GRU (improve memory, reduce vanishing gradient) |
| Use Cases | Language modeling, speech recognition, sequence tagging (with LSTM/GRU) | [END_TABLE_CONTENT]

Transformer

[START_TABLE_CONTENT] | Feature | Description |
| --- | --- |
| Structure | Uses self-attention to model dependencies across all positions at once |
| Memory | Attends to all tokens in sequence simultaneously |
| Computation | Fully parallelizable across tokens |
| Attention | Built-in self-attention and cross-attention |
| Vanishing/Exploding Gradients | Largely avoided due to residual connections and layer norm |
| Positional Info | Added explicitly via positional encoding |
| Training Time | Faster training with GPUs and large batches |
| Strengths | Handles long-range dependencies well |
| Variants | BERT (encoder-only), GPT (decoder-only), T5 (encoder-decoder), etc. |
| Use Cases | Machine translation, summarization, chatbots, text generation, etc. | [END_TABLE_CONTENT]

[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_237_0cde167b.png|0cde167bbed72f5ab92a1235b2832369 [END_IMAGE_PATH]
[START_IMAGE_PATH] /var/folders/2r/6k4lt40n56g5w9yy_dl1hjbw0000gn/T/docx_images_qxulqfzl/img_238_6caaf735.png|6caaf735d60936d3307934b043b72321 [END_IMAGE_PATH]
•  Transformer: Best for complex sequence modeling (translation, summarize, language modeling).
•  RNN: Good for moderate sequential data but suffers with long-range dependencies.
•  MLP: Best for non-sequential tasks (e.g., classification, regression) but not suited for temporal or positional reasoning.
