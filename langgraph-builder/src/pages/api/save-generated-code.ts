import fs from 'fs'
import path from 'path'
import type { NextApiRequest, NextApiResponse } from 'next'

type GenerateResponse = {
  stub?: string
  implementation?: string
  message?: string
  dir?: string
  error?: string
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<GenerateResponse>,
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const { spec, python, typescript } = req.body

  try {
    const dirPath = path.resolve(process.cwd(), '../generated_code')

    console.log('Saving files to:', dirPath)

    fs.mkdirSync(dirPath, { recursive: true })

    fs.writeFileSync(path.join(dirPath, 'spec.yml'), spec)

    if (python) {
      fs.writeFileSync(path.join(dirPath, 'stub.py'), python.stub || '')
      fs.writeFileSync(path.join(dirPath, 'implementation.py'), python.implementation || '')
    }

    if (typescript) {
      fs.writeFileSync(path.join(dirPath, 'stub.ts'), typescript.stub || '')
      fs.writeFileSync(path.join(dirPath, 'implementation.ts'), typescript.implementation || '')
    }

    console.log('Files saved successfully')

    res.status(200).json({ message: 'Files saved successfully', dir: dirPath })
  } catch (error: any) {
    console.error('Error saving files:', error)
    res.status(500).json({ error: error.message })
  }
}








// import fs from 'fs'
// import path from 'path'
// import type { NextApiRequest, NextApiResponse } from 'next'

// type GenerateResponse = {
//     stub?: string
//     implementation?: string
//     error?: string
//   }

// export default async function handler(req : NextApiRequest, res : NextApiResponse<GenerateResponse>) {
//   if (req.method !== 'POST') {
//     return res.status(405).json({ error: 'Method not allowed' })
//   }

//   const { spec, python, typescript } = req.body

//   try {
//     // Absolute path to ensure clarity
//     const dirPath = path.resolve(process.cwd(), '../generated_code')

//     console.log('Saving files to:', dirPath)

//     // Ensure directory creation
//     fs.mkdirSync(dirPath, { recursive: true })

//     fs.writeFileSync(path.join(dirPath, 'spec.yml'), spec)

//     if (python) {
//       fs.writeFileSync(path.join(dirPath, 'stub.py'), python.stub || '')
//       fs.writeFileSync(path.join(dirPath, 'implementation.py'), python.implementation || '')
//     }

//     if (typescript) {
//       fs.writeFileSync(path.join(dirPath, 'stub.ts'), typescript.stub || '')
//       fs.writeFileSync(path.join(dirPath, 'implementation.ts'), typescript.implementation || '')
//     }

//     console.log('Files saved successfully')
//     res.status(200).json({ message: 'Files saved successfully', dir: dirPath })
//   } catch (error) {
//     console.error('Error saving files:', error)
//     res.status(500).json({ error: error.message })
//   }
// }
