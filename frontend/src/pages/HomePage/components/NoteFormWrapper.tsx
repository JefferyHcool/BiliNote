import { useForm } from 'react-hook-form'
import { Form } from '@/components/ui/form.tsx'
import NoteForm from './NoteForm.tsx'

const NoteFormWrapper = () => {
  const form = useForm()

  return (
    <Form {...form}>
      <NoteForm />
    </Form>
  )
}

export default NoteFormWrapper
