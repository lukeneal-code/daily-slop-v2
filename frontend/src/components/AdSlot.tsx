import { FAKE_CREATIVES } from '../ads/creatives';
import { type AdSlotSchema, pickCreativeIndex } from '../ads/slots';

interface AdSlotProps {
  slot: AdSlotSchema;
  date: string;
}

export default function AdSlot({ slot, date }: AdSlotProps) {
  const idx = pickCreativeIndex(FAKE_CREATIVES.length, date, slot.id);
  const creative = FAKE_CREATIVES[idx];
  return (
    <aside
      className={`ad-slot ad-${slot.size}`}
      data-slot-id={slot.id}
      data-placement={slot.placement}
      aria-label="Advertisement"
    >
      <div>
        <p className="ad-slot-label">Advertisement</p>
        <p className="ad-slot-headline">{creative.headline}</p>
        <p className="ad-slot-body">{creative.body}</p>
      </div>
    </aside>
  );
}
