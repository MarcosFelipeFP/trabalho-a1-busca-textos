import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

/*
 * A interface precisa abrir com dois cliques, de um pendrive ou de uma pasta
 * baixada do Google Drive, sem servidor e sem internet. Uma página aberta por
 * file:// não consegue buscar arquivos vizinhos, então o build embute TUDO em
 * um único index.html: o JavaScript, o CSS, as fontes e o corpus.
 *
 * `base: './'` mantém qualquer referência relativa, e o proxy só serve para o
 * modo de desenvolvimento conversar com o `servidor.py` na porta 8000.
 */
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss(), viteSingleFile({ removeViteModuleLoader: true })],
  resolve: {
    alias: {
      '@fontes': fileURLToPath(new URL('./node_modules/@fontsource-variable', import.meta.url)),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 6000,
    assetsInlineLimit: 100_000_000,
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
});
