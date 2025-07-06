let activeChatId = null;
let currentZoom = 1;

window.onload = function () {
    loadChats();
    document.getElementById("user-input").addEventListener("keydown", function (e) {
        if (e.key === "Enter") sendMessage();
    });
};

function loadChats() {
    fetch("/get_chats")
        .then((res) => res.json())
        .then((data) => {
            const list = document.getElementById("chat-list");
            list.innerHTML = "";
            data.chats.forEach((chat) => {
                const li = document.createElement("li");
                li.textContent = chat.name;
                li.onclick = () => selectChat(chat.id);
                if (chat.id === activeChatId) li.style.backgroundColor = "#e74c3c";
                list.appendChild(li);
            });
        });
}

function selectChat(id) {
    activeChatId = id;
    loadChats();
    fetch(`/get_chat_history?chat_id=${id}`)
        .then((res) => res.json())
        .then((data) => {
            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML = "";
            data.messages.forEach((msg) => {
                const msgElem = document.createElement("pre");
                msgElem.textContent = msg.text;
                chatBox.appendChild(msgElem);
            });
        });
}

function createNewChat() {
    const chatName = prompt("Enter new chat name:");
    if (chatName) {
        fetch("/new_chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_name: chatName })
        })
            .then((res) => res.json())
            .then((data) => {
                loadChats();
                selectChat(data.chat_id);
            });
    }
}

function sendMessage() {
    const input = document.getElementById("user-input");
    const text = input.value.trim();
    if (!text || !activeChatId) return;
    const model = document.getElementById("model-selector").value;

    const chatBox = document.getElementById("chat-box");
    const userMsg = document.createElement("pre");
    userMsg.textContent = `User: ${text}`;
    chatBox.appendChild(userMsg);
    input.value = "";

    fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: text, chat_id: activeChatId, model: model })
    })
        .then((res) => res.json())
        .then((data) => {
            const aiMsg = document.createElement("pre");
            aiMsg.textContent = `AI: ${data.response}`;
            chatBox.appendChild(aiMsg);
            chatBox.scrollTop = chatBox.scrollHeight;
        });
}

function deleteSelectedChats() {
    if (confirm("Delete this chat?")) {
        fetch("/delete_chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ chat_id: activeChatId })
        })
            .then((res) => res.json())
            .then(() => {
                activeChatId = null;
                loadChats();
                document.getElementById("chat-box").innerHTML = "";
            });
    }
}

function changeTheme(theme) {
    switch (theme) {
        case "dark":
            document.body.style.backgroundColor = "#2c3e50";
            break;
        case "blue":
            document.body.style.backgroundColor = "#d0ebff";
            break;
        default:
            document.body.style.backgroundColor = "#f0f2f5";
    }
}

function zoomIn() {
    currentZoom += 0.1;
    document.body.style.zoom = currentZoom;
}

function zoomOut() {
    currentZoom = Math.max(0.5, currentZoom - 0.1);
    document.body.style.zoom = currentZoom;
}

function openSettings() {
    document.getElementById("settingsModal").style.display = "block";
}

function closeSettings() {
    document.getElementById("settingsModal").style.display = "none";
}

function downloadChat() {
    if (!activeChatId) return alert("Select a chat first");
    window.location.href = `/download_chat?chat_id=${activeChatId}`;
}

function startVoiceInput() {
    if (!('webkitSpeechRecognition' in window)) {
        alert("Voice recognition not supported in your browser");
        return;
    }
    const recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.onresult = function (event) {
        document.getElementById("user-input").value = event.results[0][0].transcript;
        sendMessage();
    };
    recognition.start();
}
