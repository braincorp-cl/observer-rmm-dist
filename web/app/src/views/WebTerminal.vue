<template>
  <div class="full-page-terminal">
    <div ref="xtermContainer" class="xterm-container"></div>
  </div>
</template>

<style>
.full-page-terminal {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--obs-term-bg);
}

.xterm-container {
  flex-grow: 1;
  overflow: hidden;
}
</style>

<script setup lang="ts">
import { OBS_FONT_MONO } from "@/utils/fonts";
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { useResizeObserver, useDebounceFn } from "@vueuse/core";
import { useCliWSConnection } from "@/websocket/websocket";
import "@xterm/xterm/css/xterm.css";

const xtermContainer = ref<HTMLElement | null>(null);
let term: Terminal;
const fit = new FitAddon();

// Resuelve un token --obs-* a su hex. xterm NO acepta "var(--obs-term-bg)":
// css.toColor() prueba el string contra el fillStyle de un canvas sembrado con un
// CanvasGradient (Color.ts:194-198); un valor inválido deja el gradiente puesto,
// toColor lanza, y parseColor() (ThemeService.ts:186-198) cae al default EN
// SILENCIO — el fondo quedaría negro #000000 sin ningún error en consola.
// Devolver undefined cuando el token no resuelve es deliberado: es el contrato de
// parseColor para "usa tu default", y evita escribir un hex de respaldo acá
// (V2-G02).
function obsToken(name: string): string | undefined {
  return (
    getComputedStyle(document.body).getPropertyValue(name).trim() || undefined
  );
}

const { data, send, close } = useCliWSConnection();

onMounted(() => {
  setupXTerm();
  useResizeObserver(xtermContainer, () => {
    resizeWindow();
  });
});

onBeforeUnmount(() => {
  disconnect();
});

function setupXTerm() {
  term = new Terminal({
    convertEol: true,
    fontFamily: OBS_FONT_MONO,
    fontSize: 15,
    fontWeight: 400,
    cursorBlink: true,
    // Los 16 ANSI quedan en el default de xterm (la paleta Tango). NO ES
    // ARBITRARIO, no revertir sin medir: con el default de xterm
    // (minimumContrastRatio: 1 = desactivado) solo 7 de los 16 llegaban a 4,5:1
    // sobre el fondo anterior #333, y ansi 0 (negro) quedaba en 1,00:1, o sea
    // literalmente invisible. El programa remoto ya no estaba consiguiendo el
    // color que eligió: lo estaba consiguiendo ilegible. Esta opción corrige el
    // texto a 4,5:1 contra el fondo real de cada celda en tiempo de render, así
    // que cubre también el video inverso y el 256/truecolor, que una paleta fija
    // de 16 valores no cubriría; exime los glifos de bloque y pide la mitad del
    // ratio en celdas dim. Acordado a sabiendas de que altera colores elegidos
    // por el programa remoto.
    minimumContrastRatio: 4.5,
    theme: {
      background: obsToken("--obs-term-bg"),
      foreground: obsToken("--obs-on-dark"),
      cursor: obsToken("--obs-on-dark"),
      cursorAccent: obsToken("--obs-term-bg"),
    },
  });

  term.loadAddon(fit);
  term.open(xtermContainer.value!);
  fit.fit();
  term.onData((data) => {
    send(JSON.stringify({ action: "ormmcli.input", data: { input: data } }));
  });
}

const resizeWindow = useDebounceFn(() => {
  fit.fit();
  const dims = { cols: term.cols, rows: term.rows };
  send(JSON.stringify({ action: "ormmcli.resize", data: dims }));
}, 300);

function disconnect() {
  term.dispose();
  close();
  send(JSON.stringify({ action: "ormmcli.disconnect" }));
}

interface WSOrmmCliOutput {
  output: string;
  messageId: string;
}

watch(data, (newValue) => {
  if (newValue.action === "ormmcli.output") {
    const incomingData = newValue.data as WSOrmmCliOutput;
    term.write(incomingData.output);
  }
});
</script>
