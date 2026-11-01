import Focus from '../../components/variants/focus';
import { loadDataset } from '../../lib/load-dataset';

export const dynamic = 'force-static';

export default async function Page() {
  return <Focus dataset={await loadDataset()} />;
}
