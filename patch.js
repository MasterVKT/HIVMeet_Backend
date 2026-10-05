const fs = require('fs');
const files = [
  'D:/Projets/HIVMeet/env/hivmeet_backend/.gemini/settings.json',
  'D:/Projets/HIVMeet/hivmeet/.gemini/settings.json'
];
for (const file of files) {
  if (!fs.existsSync(file)) continue;
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  for (const hookType in data.hooks) {
    for (const rule of data.hooks[hookType]) {
      for (const hook of rule.hooks) {
        if (hook.command && hook.command.startsWith('bash ')) {
          const script = hook.command.substring(5);
          hook.commandWindows = '\"C:/Program Files/Git/bin/bash.exe\" ' + script;
        }
      }
    }
  }
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}
console.log('Done');
