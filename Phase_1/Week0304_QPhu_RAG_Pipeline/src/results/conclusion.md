In the RAG system 

- when we manually perform the RAG system, many things in the performance still like and nearly the same as the other framework they did (like the coding flow and the generation timing phase)
- but the main difference is that when we need to generating the embedding + storing the embedding (indexing them in the Vector Database) + retrieving the relevant documents --> those things in the popular framework they have been better because i think that they have do some optimizations on there vectorstore and the algorithm for getting the 'nearest' vectors to our vector queries have been optimized to be faster but still correct --> that is, those popular framework they have consider for us about the trade-offs between the time of creating, indexing, retrieving documents --> the things that we would take millions of times to manually consider from scratch

==> so my suggestion would be 

- we manually the processing data --> because our data is multimodal data so we need to considering them by ourselves by what our expectations are
- we manually choosing the model for embeddings --> considering by experiments
- we manually choosing the vector storage and the database for storing the multimodal data of us
- we SHOULD USE some popular framework / cloud database / vectorstorage and use the one that have been optimized already
- we SHOULD USE some LLM model such that they have their own knowledge trained from the early of 2025 --> for this, we EXPECT that the newer the model, the more they could understand our query better to help us at the step of NORMALIZING / REWRITING the user query
- we SHOULD USE some LLM model such that they have the REASONING score on benchmark good and high because --> because later maybe the user could enter a multi-intent queries so we should have the PLANNING STEPS for splitting the query to multiple subqueries for better getting the response OR we could think of executing the LLM and our system in a loop with the CONDITION of for example the current chunks are enough for answering about 80% of the questions
