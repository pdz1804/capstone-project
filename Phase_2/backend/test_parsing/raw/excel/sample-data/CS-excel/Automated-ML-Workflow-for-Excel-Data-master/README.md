
# Automated Machine Learning Workflow for Excel Data
![image ult](https://github.com/AnirudhM2110/Automated-Machine-Learning-Workflow-for-Excel-Data/blob/master/Title%20image.png?raw=true)
This repository offers a comprehensive solution for performing data analysis using machine learning techniques on data stored in Excel files. The goal is to provide users with an easy-to-use command-line interface (CLI) to preprocess, analyze, and visualize data using a variety of machine learning models, including both **unsupervised** (PCA, clustering) and **supervised** (classification) learning methods.

## Key Features

### 1. **Loading and Exploring Excel Data**

-   The code supports loading data from Excel files located in the current directory, and it allows users to interactively select the desired Excel file for analysis.
-   If the file contains multiple sheets, the user is prompted to choose a sheet for further processing.
-   After selecting the sheet, the available columns in the dataset are displayed, allowing the user to decide which columns to ignore or use as target labels in supervised learning.

### 2. **Data Preprocessing**

-   Data preprocessing is essential for improving the quality and performance of machine learning models. This project provides flexible preprocessing options, including:
    -   **Standardization (Autoscaling)**: Scales the features so that they have a mean of 0 and a standard deviation of 1.
    -   **Normalization (Min-Max Scaling)**: Scales the data so that it falls within a specific range (typically 0-1) after applying autoscaling.
    -   **No Preprocessing**: Allows users to skip preprocessing if they have already preprocessed the data.

### 3. **Unsupervised Learning**

-   **Principal Component Analysis (PCA)**: A technique to reduce the dimensionality of the data while preserving as much variance as possible. PCA is used for exploratory data analysis and visualization.
    
    -   Visualizes the transformed data in the form of a scatter plot showing the first two principal components.
- **Clustering Algorithms**:
  - **K-Means Clustering**: 
    - Parameters:
      - n_clusters (int): Number of clusters 
     
  
  - **DBSCAN**: 
    - Parameters:
      - epsilon (float): The maximum distance between two samples for one to be considered as in the neighborhood of the other. This is the most important DBSCAN parameter. Represents the radius of the neighborhood around a point.
       
        - Smaller values create tighter, more numerous clusters
        - Larger values create fewer, more inclusive clusters
      - min_samples (int): The minimum number of samples in a neighborhood for a point to be considered as a core point

  
  - **Hierarchical Clustering**:
    - Parameters:
      - n_clusters (int): Number of clusters 
      

### 4. **Supervised Learning**

- **PLS-DA**:
  - Parameters:
   `n_components`: Number of components to keep in the model

- **Support Vector Machine (SVM)**:
  - Parameters:
    - `kernel`: Specifies the kernel type to be used in the algorithm. Determines how the data is transformed into higher dimensions
    - `C`: Regularization parameter. Controls trade-off between achieving a low training error and a low testing error
    - `gamma`: Kernel coefficient. Defines how far the influence of a single training example reaches

- **XGBoost**:
  - Parameters:
    - `n_estimators`: Number of boosting rounds. Number of trees to be built
    - `learning_rate`: Step size shrinkage. Controls how much we adjust the weights of our features at each step
    - `max_depth`: Maximum depth of a tree. Controls how deep each tree can grow during the boosting process

- **Random Forest**:
  - Parameters:
    - `n_estimators`: Number of trees in the forest
    - `max_depth`: Maximum depth of each tree
    - `min_samples_split`: Minimum samples required to split an internal node
  



### 5. **Model Evaluation**

-  After training a model, performance is evaluated using:
    
    -   **Accuracy**: The proportion of correct predictions.
    -   **Confusion Matrix**: A summary table showing the number of correct and incorrect predictions, broken down by class.
    -   **Classification Report**: A detailed report providing precision, recall, and F1-score for each class.

### 6. **Data Export and Results Saving**

-   Results from PCA, clustering, and supervised learning models can be saved to new Excel files for further analysis. This includes:
    -   **PCA-transformed data**: A file containing the data after applying PCA, allowing users to explore the reduced feature set.
    -   **Clustering results**: A file with the cluster assignments for each data point, as well as additional metadata.
    -   **Figures**: Visualizations of PCA and clustering results, including scatter plots and confidence ellipses, are saved in the `figures/` directory.

### 7. **Interactive Command-Line Interface (CLI)**

-   The code offers an interactive CLI where users are prompted to select files, sheets, preprocessing options, and machine learning models step-by-step.
-   It is designed to be easy to use, even for users without a deep background in machine learning. The options are presented in a simple, menu-driven format.

## Input File Requirements

1. File Format:
   - Must be Excel format (.xlsx)
   - File should be placed in the same directory as the script
   - Multiple sheets are supported

2. Data Structure:
   - First column: Sample labels (text or numeric)
   - Subsequent columns: Numeric data for analysis
   - Header row required
   - No missing values allowed
   - No text data in analysis columns
   - Class columns (for supervised learning) should contain categorical data


## Usage Instructions

### 1. **Installation**
Open your terminal or command-line interface:

 -  Clone the repository and enter the directory:

     ```bash
    git clone https://github.com/AnirudhM2110/Automated-Machine-Learning-Workflow-for-Excel-Data.git
    cd Automated-Machine-Learning-Workflow-for-Excel-Data
 - Install dependencies from the requirements.txt file:
      ```bash
    pip install -r requirements.txt

### 2. **Run the program**

 - Run the program from the terminal
      ```bash
    python main.py
### 3. **Selecting the Excel File**
-   Place your Excel data file in the same directory as the script 
-   The script will scan the current directory for `.xlsx` files.
-   You will be prompted to select an Excel file by entering its corresponding number.

### 4. **Choosing the Sheet**

-   If the selected Excel file contains multiple sheets, you will be prompted to choose which sheet you want to analyze.
-   If the file has only one sheet, it will be automatically selected.

### 5. **Data Preprocessing**

-   After the data is loaded, you will be given three options for preprocessing:
    -   **Standardization (Autoscaling)**
    -   **Normalization (Min-Max Scaling after autoscaling)**
    -   **No Preprocessing**

Select the preprocessing method that suits your data.

### 6. **Unsupervised Learning**

-   If you choose **unsupervised learning**, you will first apply PCA to the data. The script will visualize the first two principal components.
-   You can then choose a clustering algorithm (K-Means, DBSCAN, or Hierarchical Clustering).
-   The algorithm will be applied, and the clustering results will be visualized and saved in a new file.

### 7. **Supervised Learning**

-   If you select **supervised learning**, you will be prompted to choose a classification model (Random Forest, XGBoost, SVM, or PLS-DA).
-   The script will allow you to tune hyperparameters, split the data into training and testing sets, and train the model.
-   After training, the model's performance will be evaluated and displayed in terms of accuracy, confusion matrix, and a classification report.

### 8. **Exporting Results**

-   Once the analysis is complete, the results will be saved to new Excel files:
    -   PCA-transformed data: `pca_transformed_data.xlsx`
    -   PCA loadings: `pca_loadings.xlsx`
    -   Clustering results: `clustering_results.xlsx`
-   Any generated visualizations, such as PCA plots or clustering scatter plots, will be saved in the `figures/` directory.

## Contributing

We welcome contributions! If you have any ideas for improvements, bug fixes, or additional features, feel free to open an issue or submit a pull request.
