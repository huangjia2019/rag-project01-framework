const config = {
              development: {
                apiBaseUrl: 'http://localhost:8001'
              },
              production: {
                apiBaseUrl: 'http://api.example.com'
              },
              test: {
                apiBaseUrl: 'http://localhost:8001'
              }
            };
            
// 使用 Vite 的环境变量
const env = import.meta.env.MODE || 'development';
export const apiBaseUrl = config[env].apiBaseUrl;

console.log('Current MODE:', import.meta.env.MODE);
console.log('All env variables:', import.meta.env);

export default config[env];