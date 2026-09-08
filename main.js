// server.js
const express = require('express');
const { PythonShell } = require('python-shell');
const path = require('path');
const EventEmitter = require('events');
const bodyParser = require('body-parser');
const WebSocket = require('ws');
const fs = require('fs'); 

const app = express();
const port = 3000;

const server = require('http').createServer(app);
const wss = new WebSocket.Server({ server:server, path:'/ws_auth_status' });

let pythonProcess = null;
const cameraStateEmitter = new EventEmitter();

app.use(express.static('public')); // publicディレクトリを静的ファイルとして提供
app.use(bodyParser.urlencoded({ extended: true })); 

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 新しいエンドポイント：shu.html と tai.html へのアクセス
app.get('/shu.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'shu.html'));
});

app.get('/tai.html', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'tai.html'));
});


app.get('/start_camera_stream', (req, res) => {
    if (pythonProcess && !pythonProcess.terminated) {
    //    console.log('Camera stream already running.');
    //    return res.status(200).send('Camera stream already running.');
    //}
        pythonProcess.kill();
        pythonProcess = null;
    }

    res.writeHead(200, {
        'Content-Type': 'multipart/x-mixed-replace; boundary=frame',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
    });

    try {
        pythonProcess = new PythonShell('python_camera_feed.py', {
            mode: 'binary',
            pythonPath: '/opt/anaconda3/envs/venv_lec/bin/python' // または '/usr/bin/python3' など、環境に合わせて
        });

        pythonProcess.stdout.on('data', (data) => {
            res.write(data);
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error(`Python stderr: ${data.toString()}`);
            if (data.toString().includes("Error: Could not open camera.")) {
                cameraStateEmitter.emit('camera_error', "カメラにアクセスできません。");
            } else if (data.toString().includes("Error: encodings.pkl not found.")) {
                cameraStateEmitter.emit('camera_error', "顔認証データ(encodings.pkl)が見つかりません。");
            }
        });

        pythonProcess.on('error', (err) => {
            console.error('PythonShell error:', err);
            cameraStateEmitter.emit('camera_error', "Pythonスクリプトエラーが発生しました。");
            if (!res.headersSent) {
                res.status(500).send('Python script error');
            }
            res.end();
            pythonProcess = null;
            cameraStateEmitter.emit('camera_status', false);
            wss.clients.forEach(client => {
                if (client.readyState === WebSocket.OPEN) {
                    client.send(JSON.stringify({ recognized_names: [] }));
                }
            });
        });

        pythonProcess.on('close', (code) => {
            console.log(`Python script closed with code ${code}`);
            if (!res.headersSent) {
                 res.status(500).send('Camera stream stopped unexpectedly');
            }
            res.end();
            pythonProcess = null;
            cameraStateEmitter.emit('camera_status', false);
            wss.clients.forEach(client => {
                if (client.readyState === WebSocket.OPEN) {
                    client.send(JSON.stringify({ recognized_names: [] }));
                }
            });
        });

        cameraStateEmitter.emit('camera_status', true);

        req.on('close', () => {
            if (pythonProcess && !pythonProcess.terminated) {
                console.log('Client disconnected from stream, terminating Python process.');
                pythonProcess.kill();

                cameraStateEmitter.emit('camera_status', false);
                wss.clients.forEach(client => {
                    if (client.readyState === WebSocket.OPEN) {
                        client.send(JSON.stringify({ recognized_names: [] }));
                    }
                });
            }
        });

    } catch (error) {
        console.error('Failed to start PythonShell:', error);
        cameraStateEmitter.emit('camera_error', "Pythonスクリプトの起動に失敗しました。");
        if (!res.headersSent) {
            res.status(500).send('Failed to start Python script');
        }
        res.end();
        pythonProcess = null;
        cameraStateEmitter.emit('camera_status', false);
    }
});

app.post('/stop_camera_stream', (req, res) => {
    if (pythonProcess && !pythonProcess.terminated) {
        console.log('Terminating Python camera process.');
        pythonProcess.kill();
        pythonProcess = null;
        cameraStateEmitter.emit('camera_status', false);
        wss.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(JSON.stringify({ recognized_names: [] }));
            }
        });
        res.status(200).send('Camera stream stopped.');
    } else {
        console.log('No camera stream running.');
        res.status(200).send('No camera stream running.');
    }
});

const LOG_CSV_FILE = 'attendance_log.csv';
const CSV_HEADERS = '日時,氏名,区分\n';

app.post('/submit_button', (req, res) => {
    const buttonId = req.body.button_id;
    // hidden input から送信された名前を取得
    const recognizedPersonName = req.body.recognized_person_name; 

    console.log(`Button "${buttonId}" clicked!`);
    console.log(`Recognized Person Name from form: "${recognizedPersonName}"`);
    
    // recognizedPersonName から "_数字" の部分を削除して純粋な名前にする
    // 例: "Alice_1" -> "Alice", "Bob_2" -> "Bob"
    const cleanedName = recognizedPersonName ? recognizedPersonName.replace(/_\d+$/, '') : '不明';

    // 日時をYYYY/MM/DD HH:MM:SS 形式で取得
    const now = new Date();
    const dateTime = now.toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false // 24時間表記
    }).replace(/\//g, '/').replace(/ /g, ','); // スペースを半角に統一、スラッシュはそのまま

    let type = '';
    let redirectPath = '/';

    if(buttonId === "button1" ){
        type = '出勤';
        redirectPath = `/shu.html`;
    } else if(buttonId === "button2" ){
        type = '退勤';
        redirectPath = `/tai.html`;
    } 

    // CSVデータ行の作成
    const csvLine = `${dateTime},${cleanedName},${type}\n`;

    fs.access(LOG_CSV_FILE, fs.constants.F_OK, (err) => {
        if (err) {
            // ファイルが存在しない場合、ヘッダーを書き込む
            fs.writeFile(LOG_CSV_FILE, CSV_HEADERS + csvLine, { encoding: 'utf8' }, (writeErr) => {
                if (writeErr) {
                    console.error('Error writing CSV header and data:', writeErr);
                } else {
                    console.log('CSV file created and data written.');
                }
                // エラーの有無にかかわらずリダイレクト
                //res.redirect(`<span class="math-inline">\{redirectPath\}?name\=</span>{encodeURIComponent(cleanedName)}`);
            });
        } else {
            // ファイルが存在する場合、データを追記
            fs.appendFile(LOG_CSV_FILE, csvLine, { encoding: 'utf8' }, (appendErr) => {
                if (appendErr) {
                    console.error('Error appending data to CSV:', appendErr);
                } else {
                    console.log('Data appended to CSV file.');
                }
                // エラーの有無にかかわらずリダイレクト
                //res.redirect(`<span class="math-inline">\{redirectPath\}?name\=</span>{encodeURIComponent(cleanedName)}`);
            });
        }
    });

    // URLエンコードを忘れずに (特に日本語名の場合)
    const encodedName = encodeURIComponent(recognizedPersonName || '不明'); // 名前がない場合は「不明」を渡す

    if(buttonId === "button1" ){
        res.redirect(`/shu.html?name=${encodedName}`); // shu.htmlにリダイレクト
    } else if(buttonId === "button2" ){
        res.redirect(`/tai.html?name=${encodedName}`); // tai.htmlにリダイレクト
    } else {
        res.redirect(`/`); // 意図しないボタンIDの場合、最初のページに戻る
    }
});

app.get('/camera_status_updates', (req, res) => {
    res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
    });

    const sendStatus = (status) => {
        res.write(`data: ${JSON.stringify({ isCameraOn: status })}\n\n`);
    };

    const sendError = (message) => {
        res.write(`data: ${JSON.stringify({ error: true, message: message })}\n\n`);
    };

    sendStatus(!!pythonProcess);

    const onCameraStatusChange = (status) => sendStatus(status);
    const onCameraError = (message) => sendError(message);

    cameraStateEmitter.on('camera_status', onCameraStatusChange);
    cameraStateEmitter.on('camera_error', onCameraError);

    req.on('close', () => {
        cameraStateEmitter.off('camera_status', onCameraStatusChange);
        cameraStateEmitter.off('camera_error', onCameraError);
        res.end();
    });
});

// --- WebSocketサーバーの設定 ---
wss.on('connection', ws => {
    console.log('WebSocket client connected for auth status.');

    ws.on('message', message => {
        try {
            const data = JSON.parse(message);
            // 接続しているすべてのWebクライアントに認証結果をブロードキャスト
            wss.clients.forEach(client => {
                if (client.readyState === WebSocket.OPEN) {
                    client.send(JSON.stringify(data)); 
                }
            });
        } catch (e) {
            console.error('Failed to parse WebSocket message from Python:', message, e);
        }
    });

    ws.on('close', () => {
        console.log('WebSocket client disconnected from auth status.');
    });

    ws.on('error', error => {
        console.error('WebSocket error on auth status:', error);
    });
});

server.listen(port, () => {
    console.log(`Node.js server listening at http://localhost:${port}`);
});

