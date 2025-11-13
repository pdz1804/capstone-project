# RAG Comparison Results for: 'What is the game loop?'

--- 
# Pipeline A (OCR + BM25)
## 🔍 Retrieved Contexts
*   Nguồn: Chap_0_Introduction.pdf, Trang: 6 (Score: 10.22)
 
*   Nguồn: Chap4_AI_Minimax.pdf, Trang: 9 (Score: 7.84)
 
*   Nguồn: Chap_1_Math_Physic.pdf, Trang: 28 (Score: 7.62)
 
*   Nguồn: Chap_0_Introduction.pdf, Trang: 5 (Score: 4.87)
 
*   Nguồn: Chap_2_2D_Graphics.pdf, Trang: 18 (Score: 4.56)
 

## 🤖 LLM Summary (Text-only):
> The game loop is a fundamental structure in game development that continuously runs while the game is active. It typically consists of the following main steps:

1. **Process Inputs**: Capture and handle user inputs (e.g., keyboard, mouse, game controller).
2. **Update Game World**: Update the state of the game, including the positions and behaviors of game objects based on the inputs and game logic.
3. **Generate Outputs**: Render the updated game world to the screen, displaying the current state of the game to the player.

This loop repeats continuously, allowing the game to respond to player actions and maintain a dynamic environment. Examples of games that utilize a game loop include 2048, Caro, and Chicken Invader.

--- 
# Pipeline B (ColQwen - Multi-modal)
## 🔍 Retrieved Contexts
*   Nguồn: Chap_0_Introduction.pdf, Trang: 5 (Score: 16.1250) (Image sent to LLM)
*   Nguồn: Chap_0_Introduction.pdf, Trang: 2 (Score: 15.7500) (Image sent to LLM)
*   Nguồn: Chap_0_Introduction.pdf, Trang: 8 (Score: 13.7500) (Image sent to LLM)
*   Nguồn: Chap_0_Introduction.pdf, Trang: 6 (Score: 12.0000) (Image sent to LLM)
*   Nguồn: Chap_0_Introduction.pdf, Trang: 1 (Score: 11.8125) (Image sent to LLM)

## 🤖 LLM Summary (Multi-modal):
> The game loop is a fundamental concept in game programming that continuously runs while the game is active. It typically consists of the following steps:

1. **Process Inputs**: Capture and handle user inputs (like keyboard and mouse actions).
2. **Update Game World**: Modify the game state based on the inputs and game logic (e.g., moving characters, updating scores).
3. **Generate Outputs**: Render the updated game state to the screen, displaying the current visuals to the player.

This loop repeats until the game is no longer running. Examples of games that utilize this loop structure include 2048, Caro, and Chicken Invader.

--- 
# Pipeline C (OCR + MiniLM-L6)
## 🔍 Retrieved Contexts
*   Nguồn: Chap_0_Introduction.pdf, Trang: 5 (Score: 0.6600) 
*   Nguồn: Chap_0_Introduction.pdf, Trang: 2 (Score: 0.6345) 
*   Nguồn: Chap_2_2D_Graphics.pdf, Trang: 11 (Score: 0.4588) 
*   Nguồn: Chap4_AI_Minimax.pdf, Trang: 1 (Score: 0.4491) 
*   Nguồn: Chap_0_Introduction.pdf, Trang: 3 (Score: 0.4403) 

## 🤖 LLM Summary (Text-only):
> The game loop is a fundamental structure in game programming that continuously runs while the game is active. It typically consists of the following steps:

1. **Process Inputs**: Capture and handle user inputs (e.g., keyboard, mouse).
2. **Update Game World**: Modify the game state based on the inputs and game logic (e.g., moving characters, updating scores).
3. **Generate Outputs**: Render the updated game state to the screen, displaying graphics and other visual elements.

This loop repeats indefinitely until the game is stopped or exited. Examples of games that utilize this structure include 2048, Caro, and Chicken Invader.
