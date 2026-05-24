import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = join(dirname(fileURLToPath(import.meta.url)), "..");

function readPackageJson() {
  const packageJsonPath = join(rootDir, "package.json");
  return JSON.parse(readFileSync(packageJsonPath, "utf8"));
}

function packageInstalled(packageName) {
  return existsSync(join(rootDir, "node_modules", packageName, "package.json"));
}

try {
  const packageJson = readPackageJson();
  const packageNames = [
    ...Object.keys(packageJson.dependencies ?? {}),
    ...Object.keys(packageJson.devDependencies ?? {}),
  ];
  const missingPackages = packageNames.filter(
    (packageName) => !packageInstalled(packageName),
  );

  if (missingPackages.length > 0) {
    console.log(
      "依存パッケージが見つかりません。初回セットアップとして次を実行してください。",
    );
    console.log("");
    console.log("  npm install");
    console.log("");
    console.log("その後、もう一度 npm start を実行してください。");
    process.exit(1);
  }
} catch (error) {
  console.log("起動前チェックでエラーが発生しました。");
  console.log(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
