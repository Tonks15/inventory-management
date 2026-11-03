<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
        </div>
        <div class="budget-value">{{ money(budget) }}</div>
        <input
          v-model.number="budget"
          type="range"
          class="budget-slider"
          min="0"
          :max="maxBudget"
          :step="BUDGET_STEP"
          :aria-label="t('restocking.budget')"
        />
        <div class="budget-scale">
          <span>{{ money(0) }}</span>
          <span>{{ money(maxBudget) }}</span>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budget') }}</div>
          <div class="stat-value">{{ money(budget) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.allocated') }}</div>
          <div class="stat-value">{{ money(allocatedTotal) }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ money(remainingBudget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.longestLeadTime') }}</div>
          <div class="stat-value">{{ t('restocking.days', { count: longestLeadTime }) }}</div>
        </div>
      </div>

      <div v-if="orderSuccess" class="notice success-notice" role="status">
        <strong>{{ t('restocking.orderPlaced') }}</strong>
        {{ t('restocking.orderConfirmation', { number: orderSuccess.order_number, days: orderSuccess.lead_time_days }) }}
        <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
      </div>
      <div v-if="submitError" class="error" role="alert">{{ submitError }}</div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ recommendations.length }})</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="recommendations.length === 0 || submitting"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.emptyState') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.name') }}</th>
                <th>{{ t('restocking.table.supplier') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th>{{ t('restocking.table.demandGap') }}</th>
                <th>{{ t('restocking.table.quantity') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
                <th>{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in recommendations" :key="rec.sku">
                <td><strong>{{ rec.sku }}</strong></td>
                <td>{{ translateProductName(rec.name) }}</td>
                <td>{{ rec.supplier_name }}</td>
                <td>
                  <span :class="['badge', rec.trend]">{{ t(`trends.${rec.trend}`) }}</span>
                </td>
                <td>{{ rec.demand_gap }}</td>
                <td><strong>{{ rec.quantity }}</strong></td>
                <td>{{ money(rec.unit_cost) }}</td>
                <td><strong>{{ money(rec.line_cost) }}</strong></td>
                <td>{{ t('restocking.days', { count: rec.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency } from '../utils/currency'

const BUDGET_STEP = 100 // USD

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const items = ref([])
    const budget = ref(0)
    const submitting = ref(false)
    const submitError = ref(null)
    const orderSuccess = ref(null)

    const money = (amount) => formatCurrency(amount, currentCurrency.value)

    // Only items that are worth restocking: demand not falling and a positive gap
    const eligibleItems = computed(() =>
      items.value.filter(i => i.trend !== 'decreasing' && i.demand_gap > 0)
    )

    // Cost of fully restocking every eligible item, rounded up to the slider step
    const maxBudget = computed(() => {
      const total = eligibleItems.value.reduce((sum, i) => sum + i.demand_gap * i.unit_cost, 0)
      return Math.ceil(total / BUDGET_STEP) * BUDGET_STEP
    })

    // Greedy allocation: largest demand gap first, buying as much as the remaining
    // budget allows. Math is done in integer cents so float error can never push
    // the allocated total above the budget.
    const recommendations = computed(() => {
      let remainingCents = Math.round(budget.value * 100)
      const result = []
      const sorted = [...eligibleItems.value].sort((a, b) => b.demand_gap - a.demand_gap)
      for (const item of sorted) {
        const unitCents = Math.round(item.unit_cost * 100)
        if (unitCents <= 0) continue
        const quantity = Math.min(item.demand_gap, Math.floor(remainingCents / unitCents))
        if (quantity <= 0) continue
        remainingCents -= quantity * unitCents
        result.push({ ...item, quantity, line_cost: (quantity * unitCents) / 100 })
      }
      return result
    })

    const allocatedTotal = computed(() =>
      recommendations.value.reduce((sum, r) => sum + Math.round(r.line_cost * 100), 0) / 100
    )
    const remainingBudget = computed(() => Math.max(0, budget.value - allocatedTotal.value))
    const longestLeadTime = computed(() =>
      recommendations.value.reduce((max, r) => Math.max(max, r.lead_time_days), 0)
    )

    const loadItems = async () => {
      try {
        loading.value = true
        error.value = null
        items.value = await api.getRestockingItems()
        // Default to about half of the maximum, snapped to the step
        budget.value = Math.round(maxBudget.value / 2 / BUDGET_STEP) * BUDGET_STEP
      } catch (err) {
        error.value = t('restocking.loadError') + ': ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (submitting.value || recommendations.value.length === 0) return
      submitting.value = true
      submitError.value = null
      orderSuccess.value = null
      try {
        orderSuccess.value = await api.placeRestockOrder(
          recommendations.value.map(r => ({ sku: r.sku, quantity: r.quantity }))
        )
      } catch (err) {
        // Keep the selection intact; surface the server's message when present
        const detail = err.response?.data?.detail
        submitError.value = typeof detail === 'string'
          ? detail
          : Array.isArray(detail) && detail.length
            ? detail.map(d => d.msg).join('; ')
            : t('restocking.orderError')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadItems)

    return {
      t,
      BUDGET_STEP,
      loading,
      error,
      budget,
      maxBudget,
      recommendations,
      allocatedTotal,
      remainingBudget,
      longestLeadTime,
      submitting,
      submitError,
      orderSuccess,
      money,
      placeOrder,
      translateProductName
    }
  }
}
</script>

<style scoped>
.budget-value {
  font-size: 2.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
  margin-bottom: 0.75rem;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  color: #64748b;
  font-size: 0.813rem;
  margin-top: 0.25rem;
}

.place-order-btn {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.notice {
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.25rem;
  font-size: 0.938rem;
}

.success-notice {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
}

.success-notice a {
  color: #065f46;
  font-weight: 600;
  margin-left: 0.5rem;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #64748b;
}
</style>
