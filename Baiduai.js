const BaiduImageGenerator = require('./baidu_image_generator');

async function main() {
  const prompt = process.argv[2];
  if (!prompt) {
    console.error(JSON.stringify({ error: 'No prompt provided' }));
    process.exit(1);
  }

  const generator = new BaiduImageGenerator();
  try {
    const result = await generator.generateImage(prompt);
    console.log(JSON.stringify(result));
    await generator.close();
  } catch (error) {
    console.error(JSON.stringify({ error: error.message }));
    await generator.close();
    process.exit(1);
  }
}

main();