import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import Logo from '../Logo.vue'

describe('logo component', () => {
  it('should render', () => {
    const wrapper = mount(Logo)

    expect(wrapper.html()).toBeTruthy()
  })
})
