const { createServer } = require('node:http');
const fs = require('node:fs');

const hostname = '127.0.0.1';
const port = 3000;

/*const server = createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Hello World');
});
*/
var server = createServer();
server.on('request', getCss);

server.listen(port, hostname, () => {
  console.log(`Server running at http://${hostname}:${port}/`);
});


function getCss(req, res) {
  var url = req.url;
  console.log('url=', url)
  if ('/' == url) {
    fs.readFile('./index.html', 'UTF-8', function (err, data) {
        res.statusCode = 200;
        res.setHeader('Content-Type', 'text/html');
        res.write(data);
        res.end();
    });
  }
 } /*else if ('/css/test.css' == url) {
    fs.readFile('./css/test.css', 'UTF-8', function (err, data) {
        console.log('test.css is read.')
        res.writeHead(200, {'Content-Type': 'text/css'});
        res.write(data);
        res.end();
    });
  }else{
    console.log('unexpected url...')
    res.writeHead(200, {
        "Content-Type": "text/html"
      });
      const responseMessage = "<h1>Hello World</h1>";
      res.end(responseMessage);
  }*/
