import { Meilisearch } from "meilisearch"
import { prisma } from "./database"
import { logInfo, logError } from "./logger"

const masterKey = process.env.MEILISEARCH_MASTER_KEY
const INDEX_NAME = "suppliers"

export const meili = new Meilisearch({ host: "http://localhost:7700", apiKey: masterKey })
const index = meili.index(INDEX_NAME)

const settings = {
  displayedAttributes: ["id", "prefix", "name", "address", "city", "province", "phone_number", "email", "npwp", "items_sold", "service_area", "is_blacklisted"],
  searchableAttributes: ["name", "prefix", "items_sold", "service_area", "city", "province", "address", "email"],
  filterableAttributes: ["city", "province", "service_area", "items_sold", "is_active", "created_by", "prefix", "is_blacklisted"],
  sortableAttributes: ["name", "city", "province"],
  rankingRules: ["words", "typo", "proximity", "attribute", "sort", "exactness"],
  stopWords: ["pt", "cv", "ud", "tbk", "lainnya", "pribadi"],
  nonSeparatorTokens: [".", ",", "-"],
  separatorTokens: ["/", "\\", "&"],
}

const synonyms: Record<string, string[]> = {
  jabodetabek: ["jakarta", "depok", "tangerang", "bekasi", "bogor", "jabodetabek"],
  bekasi: ["cikarang", "kabupaten bekasi"],
  "jawa barat": ["bandung", "cimahi", "bekasi", "bogor", "jabar", "west java"],
  "jawa tengah": ["semarang", "solo", "salatiga", "magelang", "surakarta", "jateng", "central java"],
  "jawa timur": ["surabaya", "malang", "kediri", "probolinggo", "sidoarjo", "mojokerto", "jatim", "east java"],
  bali: ["denpasar", "badung", "tabanan", "klungkung", "kuta", "ubud"],
  "sumatera utara": ["medan", "binjai", "deliserdang", "langkat", "sumut", "north sumatra"],
  "dki jakarta": ["jakarta pusat", "jakarta selatan", "jakarta timur", "jakarta utara", "jakarta barat"],
  sewa: ["rental", "penyewaan"],
  forklift: ["alat angkat", "material handling"],
  excavator: ["backhoe", "beko"],
  genset: ["generator", "generator set"],
  selfloader: ["truk angkut", "truk muat sendiri"],
  trailer: ["kereta gandeng", "truk gandeng"],
  tronton: ["truk besar", "truk 3 sumbu"],
}

const typoTolerance = {
  minWordSizeForTypos: { oneTypo: 4, twoTypos: 8 },
  disableOnWords: [] as string[],
  disableOnAttributes: ["id", "npwp"],
}

export async function setupMeilisearch() {
  await index.updateSettings(settings)
  await index.updateSynonyms(synonyms)
  await index.updateTypoTolerance(typoTolerance)
  logInfo(`Settings applied to index '${INDEX_NAME}' successfully.`)
}

export async function syncMeilisearch() {
  try {
    await meili.createIndex(INDEX_NAME, { primaryKey: "id" })
    await index.deleteAllDocuments()

    const suppliers = await prisma.supplier.findMany()
    const docs = suppliers.map(supplier => {
      const doc: Record<string, unknown> = {
        ...supplier,
        phone_number: supplier.phoneNumber,
        name: `${supplier.name}, ${supplier.prefix ?? ""}`,
        items_sold: supplier.itemsSold ? supplier.itemsSold.split(",").map((s) => s.trim()) : [],
        service_area: supplier.serviceArea ? supplier.serviceArea.split(",").map((s) => s.trim()) : [],
        created_by: supplier.createdBy,
        is_blacklisted: supplier.isBlackListed ?? false,
      }
      for (const [key, value] of Object.entries(doc)) {
        if (value instanceof Date) doc[key] = value.toISOString()
        else if (value === null) doc[key] = ""
      }
      return doc
    })

    if (docs.length) await index.addDocuments(docs)
    logInfo(`Synced ${suppliers.length} suppliers to Meilisearch.`)
  } catch (e) {
    logError(`Meilisearch sync error: ${e}`)
    throw e
  }
}
