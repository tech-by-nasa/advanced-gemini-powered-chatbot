import React, { useState, useRef, useEffect } from 'react';

// Main component for the advanced Gemini-powered chatbot.
export default function App() {
    // State to hold the conversation history.
    const [messages, setMessages] = useState([
        { role: 'model', content: "Hello! I'm an advanced chatbot powered by Gemini. You can chat, upload images, or generate creative content with me.", type: 'text' }
    ]);
    // State for the user's current text input.
    const [input, setInput] = useState('');
    // State for the user's selected image file.
    const [image, setImage] = useState(null);
    // State to track if the model is currently generating a response.
    const [isTyping, setIsTyping] = useState(false);
    // Reference to the chat container for auto-scrolling.
    const chatContainerRef = useRef(null);
    // Reference to the audio element for TTS playback.
    const audioRef = useRef(null);

    // Gemini API configuration
    const apiKey = "";
    const flashApiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key=${apiKey}`;
    const ttsApiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key=${apiKey}`;

    // Helper functions for TTS audio conversion (from PCM to WAV)
    function base64ToArrayBuffer(base64) {
        const binaryString = window.atob(base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    }

    function pcmToWav(pcm16, sampleRate) {
        const numSamples = pcm16.length;
        const numChannels = 1;
        const sampleRateHz = sampleRate;
        const bitDepth = 16;
        const format = 1; // PCM
        const byteRate = sampleRateHz * numChannels * bitDepth / 8;
        const blockAlign = numChannels * bitDepth / 8;
        const dataSize = numSamples * numChannels * bitDepth / 8;
        const buffer = new ArrayBuffer(44 + dataSize);
        const view = new DataView(buffer);

        // RIFF header
        writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + dataSize, true);
        writeString(view, 8, 'WAVE');

        // fmt chunk
        writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, format, true);
        view.setUint16(22, numChannels, true);
        view.setUint32(24, sampleRateHz, true);
        view.setUint32(28, byteRate, true);
        view.setUint16(32, blockAlign, true);
        view.setUint16(34, bitDepth, true);

        // data chunk
        writeString(view, 36, 'data');
        view.setUint32(40, dataSize, true);
        let offset = 44;
        for (let i = 0; i < numSamples; i++) {
            view.setInt16(offset, pcm16[i], true);
            offset += 2;
        }
        return new Blob([view], { type: 'audio/wav' });
    }

    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    // Auto-scroll to the bottom of the chat when new messages are added.
    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [messages, isTyping]);

    // Function to handle TTS and play audio.
    const handleListen = async (text) => {
        try {
            const payload = {
                contents: [{ parts: [{ text: text }] }],
                generationConfig: {
                    responseModalities: ["AUDIO"],
                    speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: "Zephyr" } } }
                },
                model: "gemini-2.5-flash-preview-tts"
            };
            const response = await fetch(ttsApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
            const result = await response.json();
            const part = result?.candidates?.[0]?.content?.parts?.[0];
            const audioData = part?.inlineData?.data;
            if (audioData) {
                const sampleRate = 16000; // The sample rate for Gemini TTS model
                const pcmData = base64ToArrayBuffer(audioData);
                const pcm16 = new Int16Array(pcmData);
                const wavBlob = pcmToWav(pcm16, sampleRate);
                const audioUrl = URL.createObjectURL(wavBlob);
                if (audioRef.current) {
                    audioRef.current.src = audioUrl;
                    audioRef.current.play().catch(e => console.error("Autoplay failed:", e));
                }
            }
        } catch (error) {
            console.error("TTS failed:", error);
        }
    };

    // Function to handle the creative content generation (e.g., recipe).
    const handleCreativePrompt = async () => {
        setIsTyping(true);
        const userMessage = { role: 'user', content: "Please provide a recipe based on the conversation history.", type: 'text' };
        setMessages(prev => [...prev, userMessage]);

        // Construct chat history with only text content for the LLM
        const chatHistory = messages.filter(msg => msg.type === 'text').map(msg => ({
            role: msg.role === 'model' ? 'model' : 'user',
            parts: [{ text: msg.content }]
        }));

        const payload = {
            contents: chatHistory,
            generationConfig: {
                responseMimeType: "application/json",
                responseSchema: {
                    type: "OBJECT",
                    properties: {
                        "recipeName": { "type": "STRING" },
                        "ingredients": { "type": "ARRAY", "items": { "type": "STRING" } },
                        "instructions": { "type": "ARRAY", "items": { "type": "STRING" } }
                    },
                    "propertyOrdering": ["recipeName", "ingredients", "instructions"]
                }
            }
        };

        try {
            const response = await fetch(flashApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(`API call failed with status: ${response.status}`);
            const result = await response.json();
            const jsonText = result.candidates[0].content.parts[0].text;
            const recipe = JSON.parse(jsonText);

            setMessages(prevMessages => [
                ...prevMessages,
                { role: 'model', content: recipe, type: 'recipe' }
            ]);

        } catch (error) {
            console.error("Error generating recipe:", error);
            setMessages(prevMessages => [
                ...prevMessages,
                { role: 'model', content: "Sorry, I couldn't generate a recipe. Please try again.", type: 'text' }
            ]);
        } finally {
            setIsTyping(false);
        }
    };

    // Function to handle sending a message.
    const handleSendMessage = async (e) => {
        e.preventDefault();
        if ((!input.trim() && !image) || isTyping) return;

        // Add user message to history
        const userMessage = { role: 'user', content: input, type: 'text', image: image };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setImage(null);
        setIsTyping(true);

        const chatHistory = messages.map(msg => {
            const parts = [{ text: msg.content }];
            if (msg.image) {
                parts.push({
                    inlineData: {
                        mimeType: msg.image.mimeType,
                        data: msg.image.data
                    }
                });
            }
            return {
                role: msg.role === 'model' ? 'model' : 'user',
                parts
            };
        });

        // Add the new user message with potential image to the payload
        const userParts = [{ text: input }];
        if (image) {
            userParts.push({
                inlineData: {
                    mimeType: image.mimeType,
                    data: image.data
                }
            });
        }
        const payload = {
            contents: [...chatHistory, { role: 'user', parts: userParts }],
            generationConfig: {
                responseMimeType: "text/plain",
            }
        };

        try {
            const response = await fetch(flashApiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(`API call failed with status: ${response.status}`);
            const result = await response.json();
            const modelResponse = result.candidates[0].content.parts[0].text;

            setMessages(prevMessages => [
                ...prevMessages,
                { role: 'model', content: modelResponse, type: 'text' }
            ]);
        } catch (error) {
            console.error("Error fetching from Gemini API:", error);
            setMessages(prevMessages => [
                ...prevMessages,
                { role: 'model', content: "Sorry, I'm having trouble connecting right now. Please try again later.", type: 'text' }
            ]);
        } finally {
            setIsTyping(false);
        }
    };

    // Function to handle image file selection.
    const handleImageChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64Data = reader.result.split(',')[1];
                setImage({
                    data: base64Data,
                    mimeType: file.type,
                    url: reader.result
                });
            };
            reader.readAsDataURL(file);
        }
    };

    // Component to render a recipe card.
    const RecipeCard = ({ recipe }) => (
        <div className="bg-gray-700 p-4 rounded-xl shadow-lg mt-2">
            <h3 className="text-xl font-bold mb-2 text-white">{recipe.recipeName}</h3>
            <h4 className="font-semibold text-gray-300">Ingredients:</h4>
            <ul className="list-disc list-inside text-gray-400 mb-2">
                {recipe.ingredients.map((item, i) => (
                    <li key={i}>{item}</li>
                ))}
            </ul>
            <h4 className="font-semibold text-gray-300">Instructions:</h4>
            <ol className="list-decimal list-inside text-gray-400">
                {recipe.instructions.map((step, i) => (
                    <li key={i}>{step}</li>
                ))}
            </ol>
        </div>
    );

    return (
        <div className="flex flex-col h-screen bg-gray-900 text-white font-sans antialiased">
            <audio ref={audioRef} className="hidden"></audio>
            {/* Main Chat Container */}
            <div className="flex flex-col flex-1 max-w-4xl mx-auto w-full p-4 overflow-hidden">
                <div 
                    ref={chatContainerRef}
                    className="flex-1 overflow-y-auto pr-2"
                >
                    {/* Map through and display messages */}
                    {messages.map((msg, index) => (
                        <div
                            key={index}
                            className={`flex my-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            {msg.role === 'user' ? (
                                <div className="flex flex-col items-end">
                                    <div className="p-4 rounded-xl max-w-3/4 shadow-lg bg-blue-600 rounded-br-none">
                                        {msg.content}
                                    </div>
                                    {msg.image && (
                                        <div className="mt-2 w-48 h-auto overflow-hidden rounded-lg shadow-md">
                                            <img src={msg.image.url} alt="User upload" className="w-full h-full object-cover" />
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="flex flex-col items-start">
                                    {msg.type === 'text' && (
                                        <div className="p-4 rounded-xl max-w-3/4 shadow-lg bg-gray-800 rounded-bl-none flex items-center">
                                            <span>{msg.content}</span>
                                            <button 
                                                onClick={() => handleListen(msg.content)} 
                                                className="ml-4 p-2 rounded-full bg-gray-700 hover:bg-gray-600 transition-colors"
                                                title="Listen to this message"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 24 24" className="w-5 h-5">
                                                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1-3.22-2.5-4v8c1.5-.78 2.5-2.23 2.5-4zM16 1.84v2.02c4.42 1.49 7 5.09 7 9.14s-2.58 7.65-7 9.14v2.02c5.52-1.55 9-6.31 9-11.16s-3.48-9.61-9-11.16z" />
                                                </svg>
                                            </button>
                                        </div>
                                    )}
                                    {msg.type === 'recipe' && <RecipeCard recipe={msg.content} />}
                                </div>
                            )}
                        </div>
                    ))}
                    {/* Typing indicator */}
                    {isTyping && (
                        <div className="flex justify-start my-2">
                            <div className="p-4 rounded-xl bg-gray-800 animate-pulse">
                                ...
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Form */}
                <form 
                    onSubmit={handleSendMessage} 
                    className="flex items-center p-2 rounded-xl mt-4 bg-gray-800 border-2 border-transparent focus-within:border-blue-500 transition-colors"
                >
                    {/* Image Upload Button */}
                    <label htmlFor="image-upload" className="cursor-pointer p-3 text-white hover:text-blue-400 transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75L12 6L21.75 15.75M12 21L12 6M12 6L7.5 10.5M12 6L16.5 10.5" />
                        </svg>
                    </label>
                    <input id="image-upload" type="file" accept="image/*" onChange={handleImageChange} className="hidden" />

                    {/* Creative Prompt Button */}
                    <button 
                        type="button" 
                        onClick={handleCreativePrompt}
                        className="p-3 text-white hover:text-blue-400 transition-colors"
                        title="Generate a creative response (e.g., recipe)"
                    >
                        <span role="img" aria-label="sparkles" className="text-2xl">✨</span>
                    </button>

                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Type your message..."
                        className="flex-1 bg-transparent border-none outline-none text-white placeholder-gray-400 px-2 py-1"
                        disabled={isTyping}
                    />
                    <button
                        type="submit"
                        className="ml-2 bg-blue-600 text-white p-3 rounded-full hover:bg-blue-700 transition-colors disabled:bg-gray-600"
                        disabled={isTyping || (!input.trim() && !image)}
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                            className="w-6 h-6"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                            />
                        </svg>
                    </button>
                </form>
                {/* Image preview */}
                {image && (
                    <div className="flex justify-center mt-4">
                        <div className="relative w-32 h-32 rounded-lg overflow-hidden border-2 border-blue-500">
                            <img src={image.url} alt="Preview" className="w-full h-full object-cover" />
                            <button
                                onClick={() => setImage(null)}
                                className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 leading-none"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
