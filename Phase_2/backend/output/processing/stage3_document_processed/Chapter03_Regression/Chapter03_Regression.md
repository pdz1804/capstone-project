1

## Faculty of Computer Science and Engineering Ho Chi Minh City University of Technology

## Chapter 3 Data Regression

Assoc. Prof. TRAN MINH QUANG quangtran@hcmut.edu.vn http://researchmap.jp/quang

2025/9/9

## CONTENT

1. Introduction
2. Linear regression
3. Non-Linear regression
4. Applications
5. Problems with regression
6. Summary

## REFERENCES

- [1a] Jiawei Han, Micheline Kamber, and Jian Pei, 'Data Mining: Concepts and Techniques', 3rd Edition, Morgan Kaufmann Publishers, 2012.
- [1b] Tr ầ n Minh Quang, "Khai Phá D ữ Li ệ u và K ỹ Thu ậ t Phân L ớ p", NXB Đ ạ i H ọ c Qu ố c Gia TP. HCM, 2020.
- [2] David Hand, Heikki Mannila, Padhraic Smyth, 'Principles of Data Mining', MIT Press, 2001.
- [3] David L. Olson, Dursun Delen, 'Advanced Data Mining Techniques', Springer-Verlag, 2008.
- [4] Graham J. Williams, Simeon J. Simoff, 'Data Mining: Theory, Methodology, Techniques, and Applications', Springer-Verlag, 2006.
- [5] ZhaoHui Tang, Jamie MacLennan, 'Data Mining with SQL Server 2005', Wiley Publishing, 2005.
- [6] Oracle, 'Data Mining Concepts', B28129-01, 2008.
- [7] Oracle, 'Data Mining Application Developer's Guide', B28131-01, 2008.
- [8] Ian H.Witten, Eibe Frank, 'Data mining : practical machine learning tools and techniques', 2nd Edition, Elsevier Inc, 2005.
- Dr. Tran Minh Quang - quangtran@hcmut.edu.vn [9] Florent Messeglia, Pascal Poncelet &amp; Maguelonne Teisseire, 'Successes and new directions in data mining', IGI Global, 2008.

## 1. INTRODUCTION

line chart

The image is a scatter plot with a linear scale of range 0 to 3000 on the x-axis, labeled "Size (feet2)" on the y-axis. The plot is titled "Price ($1k)" and has a scale of range 0 to 4000 along the y-axis. The x-axis is labeled "Size (feet2)" and has a scale of range 0 to 3000.

The plot is a scatter plot with a linear scale of range 0 to 4000 along the y-axis, labeled "Price ($1k)". The plot is titled "Price ($1k)" and has a scale of range 0 to 4000 along the y-axis, labeled "Price ($1k)". The x-axis is labeled "Size (feet2)" and has a scale of range 0 to 3000.

<!-- image -->

+ Can we model the house price distribution based on their sizes ?
+ Can we predict a house price based on its size?

## 1. INTRODUCTION

bar chart

In this image we can see a graph with few data points.

<!-- image -->

## 1. INTRODUCTION

The market basket analysis problem

-  Can we find out association rules between products in transactions? tinned meat

other

In this image there is a diagram. There are few names on the graph.

<!-- image -->

## 1. INTRODUCTION

-  Analyzing the factors that impact on the quality of e-banking services (based on surveys from users)
-  Easy to use (+0.209)
-  Fast response (+0.261)
-  The ability to link with other billing services (+0.199)
-  Feelings of individuality (+0.15)
-  Privacy and security issues (-0.25)
-  …

## 1. INTRODUCTION

##  Regression

-  J. Han et al (2001, 2006): Regression is a statistic mechanism that allows predicting real/numeric and continuous values
-  Wiki (2009): Regression analysis is a statistic mechanism that allows estimating the correlation between independent variables
-  R. D. Snee (1977): Regression is a statistic mechanism in data analytics and building models from experiments, it allows prediction, control, and learning the rules to which data is generated.
-  Regression: Numeric data prediction (real-valued output)
-  Classification: 'prediction' for discrete values

## 1. INTRODUCTION

-  Regression model: Describe the relationship between a set of predictors/independent variables and one or some responses/dependent variables
-  Regression equation

<!-- formula-not-decoded -->

X : a set of predictors/independent variables; describes the changes of responses/dependent variables Y

Y : responses/dependent variables; Describes the interesting facts/events

θ : Regression coefficients; Describes the relative effects of X on Y

## 1. INTRODUCTION

##  Categories:

-  Linear v.s nonlinear
-  Linear in parameters: Linear association between parameters that affect Y
-  Nonlinear in parameters: Non-linear association between parameters that affect Y
-  Single variable v.s multiple variables
-  Single: X = (X 1 )  v.s. Multiple: X = (X 1 , X 2 , …, X k )
-  Parametric v.s nonparametric and semiparametric
-  Symmetric v.s asymmetric
-  Symmetric: descriptive regression models (e.g., log-linear models)

10

- Dr. Tran Minh Quang - quangtran@hcmut.edu.vn  Asymmetric: predictive regression models (e.g., generalized linear models)

## 1. INTRODUCTION

-  Parametric, nonparametric, and semiparametric
-  Parametric: regression models with finite parameters
-  Nonparametric: regression models with infinite parameters
-  Semiparametric: regression models with finite interesting parameters

| Regression model �   | Description �                 |
|----------------------|-------------------------------|
| Parametric �         | Y = θ 0 + θ 1 *X              |
| Nonparametric �      | Y = θ 0 + f (X)               |
| Semiparametric �     | Y = θ 0 + θ 1 *X 1 + f (X 2 ) |

## 2. LINEAR REGRESSION

-  Single variable (Univariate)
-  Multiple variables (Multivariate)

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Notations
-  N: size of training examples
- x: input
-  variable/feature
-  y: output/target variable
-  ( x (i) , y (i) ): i th learning sample
-  (x (1) ,y (1) ) = (2100, 450)

|   Size feet 2 ( x ) |   Price ($1k) ( y ) |
|---------------------|---------------------|
|                2100 |                 450 |
|                1416 |                 232 |
|                1534 |                 315 |
|                 852 |                 178 |

## 2.1. UNIVARIATE LINEAR REGRESSION

flow chart

In this image, we can see a graph. There is a text at the top of the image.

<!-- image -->

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Hypothesis (h): h θ (x)= θ 0 + θ 1 x =&gt; identify θ i ?
-  Method: 'try\_and\_error',  evaluate the ability of the regression line in describing sample data.

<!-- formula-not-decoded -->

1

2

θ

0

θ

=2

=0

1

3

2

1

0

0

3

3

2

1

0

0

θ

1

=0

0

θ

1

=0.5

2

3

3

other

In this image, we can see a graph. There is a number on the graph.

<!-- image -->

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Chose ( θ 0 , θ 1 ) so that h θ (x (i) ) ≃ y (i) ;    i=1…N
-  residual/prediction error
-  MSE

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

-  Cost function J( θ 0 , θ 1 ) =&gt; minimize

<!-- formula-not-decoded -->

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Examine a simple case: θ =0, h (x) = θ x

<!-- formula-not-decoded -->

line chart

The image depicts a graph with two axes. The x-axis is labeled as "x" and the y-axis is labeled as "y". The graph has a linear scale of range 0 to 3 on the x-axis, and a linear scale of range 0 to 1 on the y-axis. The graph has two lines plotted on the graph, one of which is a straight line with a positive slope. The other line is a dashed line with a negative slope. The dashed line is positioned at the bottom of the graph, while the straight line is positioned at the top.

The graph has a title at the top of the graph, which reads "x=0.5". This indicates that the x-axis is labeled as "x" and the y-axis is labeled as "y". The title is written in a clear and readable font.

The graph also has a scale labeled "0 to 3" on the y-axis

<!-- image -->

line chart

The image is a graph that shows the relationship between two variables, specifically the value of a variable called "J" and the value of another variable called "J_1" over time. The graph is labeled as "J_1" and has a scale of range 0 to 3 on the x-axis, labeled as "θ1" and has a scale of range 0 to 2 on the y-axis, labeled as "θ".

The graph shows a negative correlation between the two variables, with the value of "J" decreasing as the value of "J_1" increases. This means that as the value of "J" increases, the value of "J_1" decreases.

The graph also shows a positive correlation between the two variables, with the value of "J" increasing as the value of "J_1" decreases. This means that as the value of "J" increases, the value of "J_1"

<!-- image -->

<!-- formula-not-decoded -->

17

## 2.1. UNIVARIATE LINEAR REGRESSION

-  An example with h θ (x) = θ 0 +θ1 x

line chart

The image presents a line graph that illustrates the relationship between two variables: price and size. The x-axis represents the size in square feet, ranging from 0 to 1000 square feet. The y-axis represents the price of the item, ranging from $0 to $500.

The graph shows a clear upward trend in the relationship between the two variables. The price of the item increases as the size increases. This indicates that as the size of the item increases, the price of the item also increases.

Here is a detailed description of the graph:

- **Title**: The title of the graph is "Price ($1K) x $1000".
- **X-Axis**: The x-axis represents the size in square feet, ranging from 0 to 1000 square feet.
- **Y-Axis**: The y-axis represents the price of the item, ranging from $0

<!-- image -->

bar chart

The image is a diagrammatic representation of a light-up wire, which is a type of light-up wire used in various applications such as display screens, displays, and displays for display. The wire is depicted as a light-up wire, which is a type of wire that is used to create a light effect. The wire is shown in a wire-like manner, with a blue and yellow color scheme. The wire is shown to be suspended from a wire-like structure, which is a type of wire that is used to create a light effect. The wire is shown to be suspended from a wire-like structure, which is a type of wire that is used to create a light effect. The wire is shown to be suspended from a wire-like structure, which is a type of wire that is used to create a light effect. The wire is shown to be suspended from a wire-like structure, which is a type of wire that is used to create a light effect.

<!-- image -->

18

## Contour plots/figures

Source: Andrew Ng

1000s)

hel

(c

(for fixed           , this is a function of x)

700

600-

500

400

(in

300

200

100-

Price

XX

XX

1000

X

X

X

X

Training data

Current hypothesis

2000

3000

4000

Size (fetr)

0.5

0.4

0.3

0.2

0.1

0

-0.11

.S

-0.2

-0.3

-0.4

-0.5

-1000

-500

0

J(00, 01)

J(00, 0

.011

(function of the parameters            )

J(e。,61]

1000

1500

2000

80U

Source: Andrew Ng

500

00

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

(function of the parameters            )

line chart

The image is a graph with several lines and points. The graph is titled "Training Data" and has a legend at the bottom. The graph is titled "Size (feet²)" and has a scale labeled "0-1000" on the x-axis. The y-axis is labeled "Price ($/$ (inches2))".

The graph has a linear scale of range 0 to 1000 on the x-axis, labeled "Size (feet²)". There are five different lines plotted on the graph, each with a different color and a different value on the y-axis. The lines are labeled as follows:
- The first line is red and has a value of 0.500.
- The second line is blue and has a value of 0.200.
- The third line is green and has a value of 0.100.
- The fourth line is orange and

<!-- image -->

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

line chart

The image is a line graph titled "Price $ (in 1000s)." The x-axis represents "Size (feet²)" while the y-axis represents "Price $ (in 1000s)." The graph shows a downward trend in the price of a product over time. The graph is labeled as "Training Data" and "h(x)." The graph is labeled as "h(x) = 500."

The graph has a linear scale from 0 to 7000 on the y-axis, labeled "Price $ (in 1000s)." The x-axis is labeled "Size (feet²)" and has a scale from 0 to 1000.

The graph shows a downward trend in the price of a product over time. The price of the product decreases from 400 to 200. The price of the product decreases from 50

<!-- image -->

(function of the parameters            )

line chart

In this image, we can see a graph with different colors and the x-axis is labeled as "2000" and the y-axis is labeled as "0.5".

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

bar chart

The image is a line graph that shows the relationship between two variables, specifically the price of a product and the number of x-axis values. The x-axis is labeled "Size (feet²)" and the y-axis is labeled "Price (in (1000s)." The graph is titled "Price of a Product." The graph shows a linear trend with a positive correlation between the two variables.

The graph has a linear scale from 0 to 7000 on the y-axis, labeled "Price (in (1000s)." The graph also has a linear scale from 0 to 7000 on the x-axis, labeled "Size (feet²)."

The graph has a blue line that starts at a point labeled "0" and ends at a point labeled "7000." The line starts at the point labeled "0" and ends at the point labeled "7000."

<!-- image -->

(function of the parameters            )

line chart

The image is a graph that shows the trend of different lines over time. The lines are labeled as follows:

- **X-axis**: The x-axis represents the time in years.
- **Y-axis**: The y-axis represents the values of the lines.

The graph shows the following trends:
1. **Line 1**: The line starts at a value of 0.5 and increases to 0.55.
2. **Line 2**: The line starts at a value of 0.5 and increases to 0.56.
3. **Line 3**: The line starts at a value of 0.5 and increases to 0.57.
4. **Line 4**: The line starts at a value of 0.5 and increases to 0.58.
5. **Line 5**: The line starts at a value of 0.5 and increases

<!-- image -->

Source: Andrew Ng

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Gradient descent method =&gt; find our the point that minimize J( θ 0 , θ 1 )
-  Method:
- i. Initiate with a random parameter ( θ 0 , θ 1 ), ex. ( θ 0 =0, θ 1 =0)
- ii. Change ( θ 0 , θ 1 ) to reduce J( θ 0 , θ 1 )
- iii. Iterate step ii until J( θ 0 , θ 1 ) is (or we believe/accept that it is) minimum

map

The image is a graph that shows the temperature distribution of a cloud of particles. The x-axis represents the temperature in Kelvin, while the y-axis represents the temperature in Kelvin. The graph is titled "J (0,0,0) 1," which means it shows the temperature at 0 Kelvin, 0.0 Kelvin, and 0.0 Kelvin.

The graph shows a pattern of temperature distribution. The temperature at the top of the graph is the highest temperature, which is 3 Kelvin. The temperature at the bottom of the graph is the lowest temperature, which is 0 Kelvin. The temperature at the middle of the graph is the lowest temperature, which is 0.0 Kelvin. The temperature at the bottom of the graph is the highest temperature, which is 3.

The graph also shows a pattern of lines that are connected. These lines are connected to each other, and they are all pointing in the same direction. The lines are

<!-- image -->

Source: Andrew Ng

map

The image is a graph that shows the temperature distribution of a surface. The x-axis represents the temperature, ranging from 0 to 1, while the y-axis represents the temperature, ranging from 0 to 1. The graph shows a trend of increasing temperature as the x-axis increases, with a sharp peak at 0.2 and a gradual decrease towards the right. The graph also shows a horizontal line at 0.1, which indicates that the temperature is at its lowest point.

The graph is labeled "J(0,0,1)", which means that the temperature is measured at 0, 0.1, and 1 degrees Celsius. The x-axis is labeled "θ", which represents the temperature in degrees Celsius. The y-axis is labeled "J(0,0,1)", which represents the temperature in Joules per square meter per second.

The graph shows a clear trend of increasing temperature as the x

<!-- image -->

Source: Andrew Ng

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Gradient descent algorithm

## Repeat until convergence{

<!-- formula-not-decoded -->

Correct : Simultaneously update

<!-- formula-not-decoded -->

## Wrong:

<!-- formula-not-decoded -->

26

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Gradient descent algorithm: minimize J( θ 0 , θ 1 )

<!-- formula-not-decoded -->

map

The image is a graph that shows the temperature distribution of a certain object over a range of temperatures. The x-axis represents the temperature, ranging from 0 to 1, while the y-axis represents the temperature, ranging from 0 to 1. The graph shows a pattern of peaks and troughs, with the peaks being higher than the troughs.

The graph has a title at the top, which reads "J(0,0,1)", indicating that the x-axis is labeled with the temperature in J (Joules) and the y-axis is labeled with the temperature in J (Joules). The graph also has a scale from 0 to 1 on the x-axis, with a minimum of 0 and a maximum of 1 on the y-axis.

The graph shows a pattern of peaks and troughs, with the peaks being higher than the troughs. The peaks are more prominent in the middle of the

<!-- image -->

Source: Andrew Ng

2A

(for fixed           , this is a function of x)

J(00, 01)

J(00,0

.01

(function of the parameters            )

2000

line chart

There is a graph with different lines and there are numbers on the x-axis and the y-axis.

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

line chart

The image is a line graph that shows the price of a product over time. The x-axis represents the size of the product in feet, while the y-axis represents the price in dollars. The graph has a linear scale of range 0 to 700, with a minimum of 0 and a maximum of 700. The graph is titled "Price of a product (in 1000s)."

The graph shows a clear trend of decreasing price over time. The price starts at a low point around 0 and gradually increases to a high point around 700. The price then decreases to a low point around 400 and then increases again to a high point around 200.

There are two lines on the graph:
1. A blue line that is labeled "Current Hypothesis" and starts at a low point around 0 and gradually increases to a high point around 700.
2

<!-- image -->

(function of the parameters            )

line chart

The image is a scatter plot with four colors and a legend. The x-axis is labeled as "x" and the y-axis is labeled as "y". The plot is titled "Skewed Data". The legend is located at the top right of the plot. The x-axis is labeled as "x" and the y-axis is labeled as "y". The plot is filled with a scale from -0.5 to 0.5. The plot has a dashed line that is colored in blue. The plot has a dashed line that is colored in green. The plot has a dashed line that is colored in red. The plot has a dashed line that is colored in orange. The plot has a dashed line that is colored in yellow. The plot has a dashed line that is colored in purple. The plot has a dashed line that is colored in white.

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

(function of the parameters            )

2000

line chart

This is a graph, which is titled "Training data".

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

line chart

The image is a line graph that shows the price of a product over time. The x-axis represents the size of the product in feet, ranging from 0 to 4000. The y-axis represents the price in dollars, ranging from 0 to 700. The graph shows a downward trend in the price of the product over time.

The line on the graph starts at a low point and then gradually decreases over time. The price starts at 500 and decreases to 200. The price then increases to 4000 and then decreases to 1000. The price then decreases to 1000 and then increases to 2000. The price then decreases to 1000 and then decreases to 1000.

There are two lines on the graph:
1. A blue line that starts at 500 and decreases to 200

<!-- image -->

(function of the parameters            )

line chart

The image is a scatter plot with a white background. The plot consists of five different colors: blue, green, red, orange, and black. The x-axis is labeled as "x" and the y-axis is labeled as "y". The plot is titled "Skewed Data".

The scatter plot has a scale of range from -0.5 to 0.5 on the x-axis, and the y-axis ranges from -0.5 to 1000. The plot is labeled as "Skewed Data" and has a scale of range from -0.5 to 0.5 on the x-axis.

The plot has a legend on the right side of the plot that is labeled "Skewed Data" and has a scale of range from -0.5 to 0.5 on the x-axis. The legend is colored blue and red.

The plot has a title at the

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

line chart

The image is a line graph that shows the relationship between two variables, specifically the price of a product and the number of training data points. The x-axis represents the size of the product, ranging from 0 to 4000, while the y-axis represents the price in dollars. The graph is titled "Price $ (in 1000s)" and has a legend at the bottom right corner that indicates the number of training data points.

The graph shows a downward trend in the price of the product over time. The price starts at 4000 dollars and decreases to 2000 dollars, then increases to 5000 dollars, and finally to 3000 dollars. This indicates that the price of the product decreases as the number of training data points increases.

The graph also shows a positive correlation between the two variables. This means that as the number of training data points increases, the price of the

<!-- image -->

(function of the parameters            )

line chart

The image is a scatter plot with a white background. The plot consists of five different colors: blue, green, red, orange, and black. Each color represents a different range of values. The x-axis is labeled as "x" and the y-axis is labeled as "y". The plot is titled "Skewed Data".

The plot has a scale of range from -0.5 to 0.5 on the x-axis, and the y-axis ranges from -0.5 to 1000. The plot is labeled as "Skewed Data" and has a legend at the bottom right corner. The legend indicates that the x-axis is labeled as "x" and the y-axis is labeled as "y".

The plot is visually represented with a few different colored lines. The lines are colored in blue, green, red, orange, and black. The blue line is the most prominent, followed by the

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

line chart

The image is a line graph titled "Price (in (1000s))" with a categorical scale starting from 0 and ending at 700 on the y-axis, labeled as "Price (in (1000s)). The x-axis is labeled "Size (feet²)". The graph has a linear scale of range 0 to 700 along the y-axis, labeled as "Price (in (1000s)). The x-axis is labeled "Size (feet²)". There are two lines on the graph, one is labeled "Training data" and the other is labeled "Current hypothesis". The "Training data" line is on the left side of the graph, while the "Current hypothesis" line is on the right side. The graph shows a downward trend in the "Training data" line, reaching a value of 0 at the bottom of the graph and a value of 700 at the top

<!-- image -->

(function of the parameters            )

line chart

The image is a scatter plot with a white background. The plot has five different colors: blue, green, red, orange, and black. The x-axis is labeled as "x" and the y-axis is labeled as "y". The plot is titled "x - y". The plot is labeled as "x - y" and has a scale of range 0 to 0.5 on the x-axis, and 0 to 0.5 on the y-axis. The plot is labeled as "x - y" and has a scale of range 0 to 0.5 on the x-axis, and 0 to 0.5 on the y-axis. The plot is labeled as "x - y" and has a scale of range 0 to 0.5 on the x-axis, and 0 to 0.5 on the y-axis. The plot is labeled as "x - y" and has

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

line chart

The image is a line graph that shows the relationship between two variables, specifically the price of a product and the number of training data points. The x-axis represents the size of the product, ranging from 0 to 4000, while the y-axis represents the price in dollars. The graph is titled "Price (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000s)) (in (1000

<!-- image -->

(function of the parameters            )

line chart

The image is a scatter plot with a white background. The plot consists of five different colors: blue, green, red, orange, and black. Each color represents a different range of values. The x-axis is labeled as "x" and the y-axis is labeled as "y". The plot is titled "Skewed Data".

The plot has a scale of range from -0.5 to 0.5 on the x-axis, and the y-axis ranges from -0.5 to 0.5. The plot is labeled as "Skewed Data" and has a scale of range from -0.5 to 0.5 on the x-axis.

The plot is labeled as "Skewed Data" and has a scale of range from -0.5 to 0.5 on the x-axis. The plot is labeled as "Skewed Data" and has a scale of range from -0

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

line chart

The image is a line graph titled "Price $ (in 1000s)" with a linear scale from 0 to 700 along the y-axis, labeled as "Price $ (in 1000s)". The x-axis is labeled "Size (feet²)" and is measured from 0 to 1000. The graph shows a linear scale from 0 to 700 on the y-axis, labeled as "Price $ (in 1000s)". The graph has a blue line that is drawn from the bottom to the top of the graph. The line is labeled "Training data" and is colored red. The graph also has a legend on the right side of the graph, which is labeled "Size (feet²)" and is colored in red. The graph has a scale from 0 to 700 on the x-axis, labeled "Size (feet²)" and is measured

<!-- image -->

(function of the parameters            )

line chart

The image is a scatter plot with a white background. The plot consists of five different colors: blue, green, red, orange, and black. The x-axis is labeled as "x" and the y-axis is labeled as "y". The plot is titled "x - y". The plot is plotted with a scale of range -0.5 to 0.5 on the x-axis, and a scale of range -0.5 to 0.5 on the y-axis. The plot is labeled as "x - y" and has a scale of range -0.5 to 0.5 on the x-axis, and a scale of range -0.5 to 0.5 on the y-axis. The plot is labeled as "x - y" and has a scale of range -0.5 to 0.5 on the x-axis, and a scale of range -0.5 to 0.5

<!-- image -->

Source: Andrew Ng

<!-- formula-not-decoded -->

(for fixed           , this is a function of x)

(function of the parameters            )

bar chart

In this image, we can see a graph. On the graph, we can see the numbers. On the right, we can see the numbers. On the left, we can see the numbers. On the right, we can see the numbers. On the left, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers. On the right, we can see the numbers.

<!-- image -->

Source: Andrew Ng

## 2.1. UNIVARIATE LINEAR REGRESSION

other

In this image, we can see a diagram with some text and numbers.

<!-- image -->

## 2.1. UNIVARIATE LINEAR REGRESSION

-  Summary: Given N samples, a univariate regression model is described as follow (e i describes the change of Y which is not explainable from X)
-  Straight line form

<!-- formula-not-decoded -->

-  Parabol form

<!-- formula-not-decoded -->

-  Estimating ( θ 0 , θ 1 ) by gradient descent method or can be quickly estimated by:

<!-- formula-not-decoded -->

39

## 2.1. UNIVARIATE LINEAR REGRESSION

## Income vs Average Working Hours

line chart

The image is a line graph titled "Income Per Year (in thousands dollars)." The x-axis represents the average number of working hours per day, while the y-axis represents the slope of the line. The graph shows a linear relationship between the average number of working hours and the amount of money earned.

The graph has a scale of range 0 to 25,000 on the x-axis, labeled "Average Number of Working Hours Per Day." The y-axis is labeled "Income Per Year (in thousands dollars)." The graph shows a linear relationship between the average number of working hours and the amount of money earned.

There are two lines on the graph:
1. A straight line that starts at a value of 0 and goes up to a value of 25,000.
2. A curve that starts at a value of 0 and goes up to a value of 25,000

<!-- image -->

- Y= θ 0 + θ 1 *X1 → Y = 0.636 + 2.018*X
- Dr. Tran Minh Quang - quangtran@hcmut.edu.vn · The sign of θ 1 describes the effect direction (positive/negative) of X on Y.

40

## 2.1. UNIVARIATE LINEAR REGRESSION

2

5

3

2

5

3

4

|   Quantity Sold |   Price($) |
|-----------------|------------|
|            8500 |          2 |
|            4700 |          5 |
|            5800 |          3 |
|            7400 |          2 |
|            6200 |          5 |
|            7300 |          3 |
|            5600 |          4 |

line chart

**Image Description:**

The image is a line graph titled "Quantity Sold" with a linear scale of range 0 to 0.65 on the y-axis, labeled "Quantity." The x-axis is labeled "Price ($)" and is marked with a linear scale of range 0 to 6000.

The graph shows a downward trend in the quantity sold over the given range. The quantity sold decreases from 5000 to 3000, then from 3000 to 2000, and finally from 2000 to 1000.

The graph is drawn with a simple, clear line, and the data points are clearly marked. The graph is not overly complex, and the data points are easy to read and understand.

**Analysis:**

The graph shows a downward trend in the quantity sold over the range of 0 to 0

<!-- image -->

6

y=quantySold=9323-823*price

## 2.1. UNIVARIATE LINEAR REGRESSION

Figure 11.1, [2], pp. 372. Expired ventilation plotted against oxygen uptake in a series of trials, with fitted straight line: y = θ 0 + θ 1 x.

line chart

The image is a line graph that shows the expired ventilation (VOC) levels over time. The x-axis represents the time in hours, while the y-axis shows the VOC levels in parts per million (ppm). The graph is labeled "Expired ventilation (VOC) levels" and is labeled as "expired ventilation (VOC) levels."

The graph shows a trend of decreasing VOC levels over time. The VOC levels are shown as a linear scale from 0 to 150 ppm, with a minimum of 0 and a maximum of 150 ppm. The graph shows a significant drop in VOC levels over time, with the lowest VOC levels being around 100 ppm and the highest VOC levels being around 150 ppm.

There are two main trends in the graph:

1. **Initial Decrease**: The graph shows a gradual decrease in VOC levels over time. This is indicated by the decline in the VOC levels

<!-- image -->

42

## 2.1. UNIVARIATE LINEAR REGRESSION

Figure 11.2, [2], pp. 373. The data from Figure 11.1 with a model that includes a term in x 2 : y = θ 0 + θ 1 x + θ 2 x 2 .

line chart

The image is a line graph that depicts the expired ventilation (ETV) over time. The x-axis represents the time in hours, ranging from 0 to 4000, while the y-axis represents the Expired Ventilation (ETV) in units of liters per minute (L/min). The graph shows a continuous upward trend in the ETV over the years, with a significant increase in the years 2000 to 2005.

The graph shows a clear upward trend in the ETV over the years, with a noticeable increase from 2000 to 2005. The ETV in 2005 is significantly higher than the ETV in 2000, indicating a significant increase in the number of ventilators used.

The graph also shows a significant increase in the ETV over the years 2005 to 2007. This increase is not

<!-- image -->

43

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  The house prices is affected by several variables/factors

| Size (feet 2 )   | Number of rooms   | Floors   | Age       | Price($1K)   |
|------------------|-------------------|----------|-----------|--------------|
| 2104             | 5                 | 1        | 45        | 460          |
| 1416             | 3                 | 2        | 40        | 232          |
| y i = 1534       | + b + 3           | x i2 2   | +…+b x 30 | 315          |
| 852              | 0 1 x i1 2        | 2 1      | k ik 36   | 178          |
| …                | …                 | …        | …         | …            |

n:     number of input attributes (e.g., n = 4)

x (i) :   input (features) of the i th   training sample x j (i) :   value of attribute j in the training sample i th

y (i) :    i th  output in the training dataset

E.x.,

<!-- formula-not-decoded -->

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Hypothesis:

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

-  Presenting in a matrix form ( x 0=1 )

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Gradient descent:

<!-- formula-not-decoded -->

-  Coefficients θ ( θ ,…, θ ):  an n+1 vector
- 0 n
-  Minimize:  J( θ ) = J( θ ,…, θ )

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

## Repeat until convergence{

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

46

## 2.2. H ỒI QUI T UYẾN TÍNH Đ A B IẾN

## Repeat until convergence{

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

….

47

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Feature scaling:  to assure that all input features are in the same scale
-  E.g.,   x 1 = size (0 - 2000 feet 2 )

x

<!-- formula-not-decoded -->

- =&gt; They are not in the same scale. The convergence speed is affected because of this imbalance scaling.

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Assure that features are in the same scale

```
E.g.  x 1 = size (0-2000 feet 2 ) x
```

2 = number of bedrooms (1-5)

other

The image consists of a diagram with a circle labeled as \(\theta_{2}\) and a point labeled as \(\omega\). The circle is divided into three sections, each with a different radius. The points are connected by lines, and the lines are drawn with blue lines. The diagram is labeled as \(\theta_{2}\) and \(\omega\).

<!-- image -->

Scaled:  x

1 = size/2000

x

2 = number of bedrooms /5

other

The image consists of a diagram with a circle labeled as \theta_{2}. There is a small circle labeled as \theta_{1} located at the bottom of the circle. The diagram shows a spiral pattern with a diameter of 2. The diagram also includes a line labeled as \theta_{1} which is perpendicular to the diameter of the circle.

<!-- image -->

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Feature scaling
- Normalize all feature to a range of [-1, 1]

<!-- formula-not-decoded -->

- Ex., x 0 = 1 ;  0 ≤ x 1 ≤ 3; -2 ≤ x 2 ≤ 0.5      =&gt; OK -3 4
-  Apply normalization methods in chapter  2
- Ex.

<!-- formula-not-decoded -->

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Validate the Gradient descent algorithm
- J( θ ) must decrease after each iteration
- We can plot J( θ ) by θ for intuitively check the convergence ability of the algorithm

line chart

The image is a line graph titled "min J(θ)". The graph is titled "min J(θ)" and has a horizontal axis labeled "No. of iterations" and a vertical axis labeled "θ". The graph has a linear scale from 0 to 400 on the x-axis, and a linear scale of range 0 to 400 on the y-axis. The graph has a single line that starts at the point (0, 0) and extends upwards to the right, indicating that the graph is a linear plot.

The graph has two axes: the horizontal axis labeled "No. of iterations" and the vertical axis labeled "θ". The x-axis is labeled "θ" and the y-axis is labeled "θ". The graph has a linear scale of range 0 to 400 on the x-axis, and a linear scale of range 0 to 400 on the y-axis

<!-- image -->

No. of iterations

## 2.2. MULTIVARIATE LINEAR REGRESSION

##  Un-converged gradient descent

52

- α too small:

slow convergence

- α too large:

J( θ ) may not reduce at each

iteration

=&gt; the algorithm may no converge

- try α : 0.001, 0.003, 0.01, 0.03, 0.1, 0.3,…

line chart

In this image, we can see a graph. There are two graphs, one is a blue graph and the other is a red graph. There are some numbers on the graph. There is a title at the top of the image. There is a line on the graph. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title. There is a graph with a title.

<!-- image -->

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Use normal equation to identify θ

Gradient Descent

other

The image is a graph depicting the distribution of a particular variable over time. The graph consists of two main components: a horizontal axis labeled "θ" and a vertical axis labeled "θ", which is the range of the variable. The graph shows a general upward trend in the distribution of the variable, with a significant peak in the middle of the graph. The graph also includes a red line that appears to be a linear or curved line, indicating a linear or curved trend.

The graph is labeled as "θ" and "θ", and the x-axis is labeled "θ" and the y-axis is labeled "θ". The graph is not explicitly labeled, but it is clear that the graph is a graphical representation of the distribution of a variable over time.

The graph is not explicitly labeled, but it is clear that the graph is a graphical representation of the distribution of a variable over time. The graph is not explicitly labeled, but it is clear that the graph is

<!-- image -->

<!-- formula-not-decoded -->

## 2.2. MULTIVARIATE LINEAR REGRESSION

Examples:  N = 4, X: an Nx(n+1) matrix; y: an Nx1 matrix

|    |   size (feet 2 ) |   No. of rooms |   Floors |   Years |   Price ($1K) |
|----|------------------|----------------|----------|---------|---------------|
|  1 |             2104 |              5 |        1 |      45 |           460 |
|  1 |             1416 |              3 |        2 |      40 |           232 |
|  1 |             1534 |              3 |        2 |      30 |           315 |
|  1 |              852 |              2 |        1 |      36 |           178 |

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Given a training dataset: N examples, n features

## Gradient descent

-  must select α
-  needs a large number of iterations
-  workable event with a large n (e.g., n = 10 6 )

## Normal equation

-  don't need to select α
-  don't need iterations
-  Must compute (X T X) -1
-  May not work when n is large (when n = 10 4  then gradient descent  should be used)

## 2.2. MULTIVARIATE LINEAR REGRESSION

-  Note: the non-invertible issue in the normal equation method, i.e., (X T X) is not invertible
-  Resolve:
- Check the linear dependence of variables. Ex., the size in meter (x 1 ) and the size in feet (x 2 ) =&gt; remove dependent variables
- Too much features (n &gt; N). Ex., n = 20, N = 10 =&gt; reduce the number of features; find surrogate features; correct more data samples,…

## 2.2. MULTIVARIATE LINEAR REGRESSION

##  Another example:

|   Quantity Sold |   Price($) |   Advertising ($) |
|-----------------|------------|-------------------|
|            8500 |          2 |              2800 |
|            4700 |          5 |               200 |
|            5800 |          3 |               400 |
|            7400 |          2 |               500 |
|            6200 |          5 |              3200 |
|            7300 |          3 |              1800 |
|            5600 |          4 |               900 |

## 2.2. MULTIVARIATE LINEAR REGRESSION

| Regression Statistics   |   Regression Statistics |
|-------------------------|-------------------------|
| Multiple R              |                0.980681 |
| R Square                |                0.96174  |
| Adjusted R Square       |                0.942604 |
| Standard Error          |              310.524    |
| Observations            |                7        |

| �               |   Coefficie nts |   Standard Error |     t Stat | P-value           |    Lower 95% |   Upper 95% |   Lower 95.0% | Upper 95.0%   |
|-----------------|-----------------|------------------|------------|-------------------|--------------|-------------|---------------|---------------|
| Intercept       |      8536.21    |       8536.21    | 386.912    | 22.06243 2.5E-05  |  7461.97     | 9610.45     |   7461.98     | 58 9610.453   |
| Price($)        |      -835.72    |       -835.72    |  99.653    | -8.38632 0.001106 | -1112.4      | -559.041    |  -1112.4      | -559.041      |
| Advertising ($) |         0.59223 |          0.59223 |   0.104347 | 5.675579 0.004755 |     0.302515 |    0.881942 |      0.302515 | 0.881942      |

other

In this image, there is a table with some numbers and text.

<!-- image -->

## 3. NON-LINEAR REGRESSION

-  Y = f(X, θ )
-  Y is a non-linear function in terms of relationship between parameters θ .
-  Ex: Exponential, logarithmic function, Gauss, …

<!-- formula-not-decoded -->

-  Identify optimal θ : Optimization algorithms
-  Local optimization
-  Global optimization (using sum of squared residuals/errors)

## 4. APPLICATIONS

-  Data mining
-  Data preprocessing: Smoothing, noise removal,…
-  Mining tasks: numerical-values prediction, descriptive analysis
-  Apply in many domains: biology, agriculture, social issues, economy, business, finances, insurance, e-commerce, marketing, security, science, robotics, control systems, automation,…

## 5. ISSUES IN REGRESSION

##  Assumptions

-  Data distribution: the relationship between predictors and dependent variables
-  Independence of  predictors
-  Continuous values of variables (both predictor &amp; responses)
-  Errors: How to identify them?
-  The amount of data processed is not large
-  How to identify the regression model
-  Advanced techniques for regression:
-  Artificial Neural Network (ANN)
-  Support Vector Machine (SVM)

## 5. ISSUES IN REGRESSION

-  Evaluation of a regression model:
-  Collect new data to evaluate the prediction results
-  Use the existing data (as testing dataset) for evaluation
-  Data splitting
-  Training data: To build the model
-  Testing data  validate/evaluate the model
-  K-fold cross-validation
-  Iterate k times:
-  Training data: (k-1) portions of data
-  Test data: the k th  portion of data  accuracy
-  Average(accuracy) of k times

## 5. ISSUES IN REGRESSION

-  Evaluation of the regression model:
-  Accuracy
-  Sum of squared errors (SSE)
- -&gt; Overall measure of errors: smaller is better

<!-- formula-not-decoded -->

-  Mean squared error (MSE): measure of the variability in the response variable left unexplained by the regression: smaller is better

<!-- formula-not-decoded -->

(n: sample size, m: number of regression coefficients)

## 5. ISSUES IN REGRESSION

##  Accuracy (Con't)

-  The standard error of the estimate (S)
-  Đánh giá sai s ố thông th ườ ng trong quá trình d ự đoán , s ự sai l ệ ch gi ữ a giá tr ị d ự đoán và giá tr ị th ự c c ủ a bi ế n đáp ứ ng
-  Measure the common error in the prediction process. It is the mean difference between the predicted and the actual values.
-  Presents the precision of the prediction generated by the regression model

<!-- formula-not-decoded -->

<!-- formula-not-decoded -->

## 5. ISSUES IN REGRESSION

-  Factors affect the success of building regression models
-  Proper problem formulation
-  Selection of important variables and model form
-  Good dataset (both in volume and quality)
-  The use of good coefficient estimation procedures (e.g., gradient descent)
-  Model validation techniques

## 6. SUMMARY

-  Regression
-  A statistical technique, applied to continuous attributes/features
-  Simple yet useful, applicable in various domains
-  One of example showing the contribution of statistics in data mining
-  Types: Linear/non-linear, Univariate/Multivariate, Parametric/Non-parametric/Semi-parametric, Symmetric/Assymetric

logo

Q&A

<!-- image -->

quangtran@hcmut.edu.vn

2025/9/9