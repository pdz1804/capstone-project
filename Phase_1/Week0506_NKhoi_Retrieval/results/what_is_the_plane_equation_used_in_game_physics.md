# RAG Comparison Results for: 'What is the plane equation used in game physics?'


# Pipeline A (OCR + BM25)
## 🔍 Retrieved Contexts
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 26 (Score: 10.94)
 
* Nguồn: Chap_0_Introduction.pdf, Trang: 6 (Score: 10.22)
 
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 37 (Score: 9.41)
 
* Nguồn: Chap4_AI_Minimax.pdf, Trang: 9 (Score: 7.84)
 
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 28 (Score: 7.62)
 

## 🤖 LLM Summary (Text-only):
> The plane equation used in game physics is given by the formula:

\[ P \cdot n + d = 0 \]

where:
- \( P \) is a point on the plane,
- \( n \) (often represented as \(\hat{n}\)) is the normal vector of the plane,
- \( d \) is the distance from the origin to the plane along the normal vector. 

This equation is fundamental in determining the relationship between points in space and the plane in 3D environments, which is crucial for collision detection and other physics calculations in games.

# Pipeline B (ColQwen - Multi-modal)
## 🔍 Retrieved Contexts
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 25 (Score: 15.2500) (Image sent to LLM)
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 26 (Score: 15.0625) (Image sent to LLM)
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 49 (Score: 15.0625) (Image sent to LLM)
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 2 (Score: 14.6875) (Image sent to LLM)
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 1 (Score: 13.8750) (Image sent to LLM)

## 🤖 LLM Summary (Multi-modal):
> The plane equation used in game physics is represented as:

\[ P \cdot \hat{n} + d = 0 \]

Where:
- \( P \) is a point on the plane.
- \( \hat{n} \) is the normal vector of the plane.
- \( d \) is the distance from the origin to the plane.

This equation is fundamental for determining interactions with planes in 3D space, such as collision detection and physics-based movement.

# Pipeline C (OCR + MiniLM-L6)
## 🔍 Retrieved Contexts
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 25 (Score: 0.5353) 
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 1 (Score: 0.5044) 
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 26 (Score: 0.4791) 
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 49 (Score: 0.4614) 
* Nguồn: Chap_1_Math_Physic.pdf, Trang: 2 (Score: 0.4586) 

## 🤖 LLM Summary (Text-only):
> The plane equation used in game physics is typically represented as:

\[ P \cdot n + d = 0 \]

Where:
- \( P \) is a point on the plane,
- \( n \) is the normal vector of the plane,
- \( d \) is the distance from the origin to the plane along the normal vector.

In a structured format, it can be defined as:

```plaintext
struct Plane {
    Vector3 normal; // The normal vector of the plane
    float d;       // The distance from the origin to the plane
};
```

This equation is fundamental in collision detection and physics-based movement in game development.
