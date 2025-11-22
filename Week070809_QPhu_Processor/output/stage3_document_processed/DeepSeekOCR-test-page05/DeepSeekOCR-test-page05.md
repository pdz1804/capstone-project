Figure3|ThearchitectureofDeepSeek-OCR.DeepSeek-OCRconsistsofaDeepEncoderand aDeepSeek-3B-MoEdecoder.DeepEncoderisthecoreofDeepSeek-OCR,comprisingthree components:aSAM[17]forperceptiondominatedbywindowattention,aCLIP[29]for knowledgewithdenseglobalattention,and a16xtokencompressorthatbridgesbetweenthem.

bar chart

In this image, we can see some text and some images.

<!-- image -->

## 3.Methodology

## 3.1.Architecture

AsshowninFigure3,DeepSeek-OCRenjoys aunifiedend-to-endVLM architectureconsisting ofan encoder andadecoder.Theencoder(namelyDeepEncoder)isresponsibleforextracting imagefeaturesand tokenizing aswell ascompressingvisualrepresentations.The decoderis usedforgeneratingtherequiredresultbasedonimagetokensandprompts.DeepEncoderis approximately380Minparameters,mainlycomposedofan80MSAM-base[17]anda300M CLIP-large[29]connectedinseries.Thedecoderadoptsa3BMoE[19,20]architecturewith570M activatedparameters.Inthefollowingparagraphs,wewilldelveintothemodelcomponents, dataengineering,andtrainingskills.