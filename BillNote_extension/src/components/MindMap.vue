<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { absolutizeMarkdownImages, stripSourceLink } from '~/logic/api'

const props = defineProps<{ markdown: string }>()

const svgRef = ref<SVGSVGElement | null>(null)
let mm: Markmap | null = null
const transformer = new Transformer()

function render() {
  if (!svgRef.value)
    return
  const md = absolutizeMarkdownImages(stripSourceLink(props.markdown || ''))
  const { root } = transformer.transform(md)
  if (!mm)
    mm = Markmap.create(svgRef.value, undefined, root)
  else
    mm.setData(root).then(() => mm?.fit())
}

onMounted(render)
watch(() => props.markdown, render)
</script>

<template>
  <div class="w-full h-full bg-white rounded border overflow-hidden">
    <svg ref="svgRef" class="w-full h-full" />
  </div>
</template>
