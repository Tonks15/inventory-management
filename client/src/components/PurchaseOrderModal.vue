<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ mode === 'view' ? t('purchaseOrder.viewTitle') : t('purchaseOrder.createTitle') }}
            </h3>
            <button class="close-button" type="button" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <!-- Item context -->
            <div class="item-context">
              <div class="item-name">{{ translateProductName(backlogItem.item_name) }}</div>
              <div class="item-meta">
                <span>{{ t('purchaseOrder.sku') }}: <span class="mono">{{ backlogItem.item_sku }}</span></span>
                <span>{{ t('purchaseOrder.shortage') }}: {{ shortage }} {{ t('purchaseOrder.units') }}</span>
              </div>
            </div>

            <!-- Create mode -->
            <form v-if="mode === 'create'" id="po-form" class="po-form" @submit.prevent="submit">
              <div class="form-group">
                <label for="po-supplier">{{ t('purchaseOrder.supplierName') }}</label>
                <input id="po-supplier" v-model="form.supplier_name" type="text" required />
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label for="po-quantity">{{ t('purchaseOrder.quantity') }}</label>
                  <input id="po-quantity" v-model.number="form.quantity" type="number" min="1" step="1" required />
                </div>
                <div class="form-group">
                  <label for="po-unit-cost">{{ t('purchaseOrder.unitCost') }}</label>
                  <input id="po-unit-cost" v-model.number="form.unit_cost" type="number" min="0.01" step="0.01" required />
                </div>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label for="po-date">{{ t('purchaseOrder.expectedDelivery') }}</label>
                  <input id="po-date" v-model="form.expected_delivery_date" type="date" required />
                </div>
                <div class="form-group">
                  <label>{{ t('purchaseOrder.totalCost') }}</label>
                  <div class="readonly-total">{{ formatMoney(formTotal) }}</div>
                </div>
              </div>

              <div class="form-group">
                <label for="po-notes">{{ t('purchaseOrder.notes') }}</label>
                <textarea id="po-notes" v-model="form.notes" rows="3"></textarea>
              </div>

              <div v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</div>
            </form>

            <!-- View mode -->
            <div v-else>
              <div v-if="loading" class="state-message">{{ t('purchaseOrder.loading') }}</div>
              <div v-else-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.supplierName') }}</div>
                  <div class="info-value">{{ purchaseOrder.supplier_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.status') }}</div>
                  <div class="info-value"><span class="badge">{{ purchaseOrder.status }}</span></div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.quantity') }}</div>
                  <div class="info-value">{{ purchaseOrder.quantity }} {{ t('purchaseOrder.units') }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.unitCost') }}</div>
                  <div class="info-value">{{ formatMoney(purchaseOrder.unit_cost) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.totalCost') }}</div>
                  <div class="info-value">{{ formatMoney(viewTotal) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.expectedDelivery') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.expected_delivery_date) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.createdAt') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.created_date) }}</div>
                </div>
                <div v-if="purchaseOrder.notes" class="info-item full-width">
                  <div class="info-label">{{ t('purchaseOrder.notes') }}</div>
                  <div class="info-value notes">{{ purchaseOrder.notes }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button class="btn-secondary" type="button" @click="close">{{ t('common.close') }}</button>
            <button
              v-if="mode === 'create'"
              class="btn-primary"
              type="submit"
              form="po-form"
              :disabled="submitting"
            >
              {{ submitting ? t('purchaseOrder.submitting') : t('purchaseOrder.submit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const { t, translateProductName } = useI18n()

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  },
  backlogItem: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'create',
    validator: (value) => ['create', 'view'].includes(value)
  }
})

const emit = defineEmits(['close', 'po-created'])

const form = ref({
  supplier_name: '',
  quantity: 1,
  unit_cost: null,
  expected_delivery_date: '',
  notes: ''
})
const purchaseOrder = ref(null)
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

const shortage = computed(() => {
  if (!props.backlogItem) return 0
  return Math.max(0, props.backlogItem.quantity_needed - props.backlogItem.quantity_available)
})

const formTotal = computed(() => (Number(form.value.quantity) || 0) * (Number(form.value.unit_cost) || 0))

// Prefer the server-provided total, fall back to quantity * unit_cost
const viewTotal = computed(() => {
  const po = purchaseOrder.value
  if (!po) return 0
  return po.total_cost ?? po.quantity * po.unit_cost
})

const resetForm = () => {
  form.value = {
    supplier_name: '',
    // Default to the shortage; at least 1 so the field is valid
    quantity: Math.max(1, shortage.value),
    unit_cost: null,
    expected_delivery_date: '',
    notes: ''
  }
  errorMessage.value = ''
  submitting.value = false
}

const loadPurchaseOrder = async () => {
  purchaseOrder.value = null
  errorMessage.value = ''
  if (!props.backlogItem) return
  loading.value = true
  // Capture the id so a stale response (modal reopened for another item) is ignored
  const requestedId = props.backlogItem.id
  try {
    const result = await api.getPurchaseOrderByBacklogItem(requestedId)
    if (props.backlogItem?.id === requestedId) purchaseOrder.value = result
  } catch (err) {
    console.error('Failed to load purchase order:', err)
    if (props.backlogItem?.id === requestedId) errorMessage.value = t('purchaseOrder.loadError')
  } finally {
    if (props.backlogItem?.id === requestedId) loading.value = false
  }
}

// Reinitialise whenever the modal opens (or is reused for a different item/mode)
watch(
  () => [props.isOpen, props.backlogItem?.id, props.mode],
  () => {
    if (!props.isOpen || !props.backlogItem) return
    if (props.mode === 'view') {
      loadPurchaseOrder()
    } else {
      resetForm()
    }
  },
  { immediate: true }
)

const submit = async () => {
  if (submitting.value || !props.backlogItem) return
  const f = form.value
  const quantity = Number(f.quantity)
  const unitCost = Number(f.unit_cost)

  if (!f.supplier_name.trim() || !f.expected_delivery_date) {
    errorMessage.value = t('purchaseOrder.validationRequired')
    return
  }
  if (!Number.isInteger(quantity) || quantity <= 0) {
    errorMessage.value = t('purchaseOrder.validationQuantity')
    return
  }
  if (!(unitCost > 0)) {
    errorMessage.value = t('purchaseOrder.validationUnitCost')
    return
  }

  submitting.value = true
  errorMessage.value = ''
  try {
    const result = await api.createPurchaseOrder({
      backlog_item_id: props.backlogItem.id,
      supplier_name: f.supplier_name.trim(),
      quantity,
      unit_cost: unitCost,
      expected_delivery_date: f.expected_delivery_date,
      notes: f.notes.trim()
    })
    emit('po-created', result)
  } catch (err) {
    console.error('Failed to create purchase order:', err)
    // Surface the backend's message (e.g. duplicate PO) when available
    const detail = err?.response?.data?.detail
    errorMessage.value = typeof detail === 'string' ? detail : t('purchaseOrder.createError')
  } finally {
    submitting.value = false
  }
}

const close = () => {
  emit('close')
}

const formatMoney = (amount) => {
  const n = Number(amount)
  if (!isFinite(n)) return 'N/A'
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const formatDate = (dateString) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return 'N/A'
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}

.item-context {
  padding-bottom: 1rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid #e2e8f0;
}

.item-name {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 0.25rem;
}

.item-meta {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  font-size: 0.875rem;
  color: #64748b;
}

.mono {
  font-family: 'Monaco', 'Courier New', monospace;
}

.po-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.form-group label,
.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.form-group input,
.form-group textarea {
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  font-family: inherit;
  color: #0f172a;
  background: white;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #64748b;
  box-shadow: 0 0 0 3px rgba(100, 116, 139, 0.15);
}

.form-group textarea {
  resize: vertical;
}

.readonly-total {
  padding: 0.625rem 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 600;
  color: #0f172a;
}

.error-message {
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 0.875rem;
}

.state-message {
  padding: 1.5rem 0;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.info-item.full-width {
  grid-column: 1 / -1;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
}

.info-value.notes {
  white-space: pre-wrap;
  font-weight: 400;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.625rem;
  border-radius: 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: capitalize;
}

.modal-footer {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  background: #0f172a;
  border: 1px solid #0f172a;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1e293b;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
